import email
import logging
import re
import shlex
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
import aioimaplib
import aiosmtplib
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models import Account, Attachment, Message
from app.repositories import write_log
from app.security import decrypt

logger = logging.getLogger(__name__)

def _text(value): return str(make_header(decode_header(value or "")))
def _message_bytes(lines) -> bytes | None:
    """Возвращает MIME-тело из FETCH-ответа, не полагаясь на первый заголовок письма."""
    candidates = [line for line in lines if isinstance(line, bytes) and (b"\r\n" in line or b"\n" in line)]
    return max(candidates, key=len) if candidates else None
def _mailboxes(lines) -> list[tuple[str, str]]:
    """Разбирает LIST и возвращает пары (IMAP-имя, локальное имя папки)."""
    result: list[tuple[str, str]] = []
    special = {"\\inbox": "INBOX", "\\sent": "Sent", "\\drafts": "Drafts", "\\trash": "Trash", "\\junk": "Spam"}
    for line in lines:
        if not isinstance(line, bytes): continue
        match = re.match(r"^(?:LIST\s+)?\((?P<flags>[^)]*)\)\s+(?:NIL|\"[^\"]*\")\s+(?P<name>.+)$", line.decode(errors="replace"))
        if not match or "\\noselect" in match.group("flags").lower(): continue
        try: name = shlex.split(match.group("name"))[0]
        except (ValueError, IndexError): continue
        flags = match.group("flags").lower(); local_name = next((value for flag, value in special.items() if flag in flags), "INBOX" if name.upper() == "INBOX" else name)
        result.append((name, local_name))
    return result
def _parse(raw: bytes, account_id: int, folder: str, uid: int, flags: bytes = b"") -> Message:
    msg = email.message_from_bytes(raw)
    item = Message(account_id=account_id, folder=folder, uid=uid, message_id=msg.get("Message-ID"), subject=_text(msg.get("Subject")) or "(без темы)", sender=_text(msg.get("From")), recipients=_text(msg.get("To")), cc=_text(msg.get("Cc")), bcc=_text(msg.get("Bcc")), size=len(raw), html_body="", text_body="", is_read=b"\\Seen" in flags, is_important=b"\\Flagged" in flags)
    try: item.sent_at = parsedate_to_datetime(msg.get("Date")) if msg.get("Date") else None
    except (TypeError, ValueError): item.sent_at = None
    for part in msg.walk():
        payload = part.get_payload(decode=True) or b""; filename = part.get_filename()
        if filename: item.attachments.append(Attachment(filename=_text(filename), content_type=part.get_content_type(), size=len(payload), content=payload))
        elif part.get_content_type() in ("text/plain", "text/html"):
            text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
            if part.get_content_type() == "text/html": item.html_body += text
            else: item.text_body += text
    return item

class MailService:
    async def check(self, account: Account):
        result = {"imap": {"ok": False}, "smtp": {"ok": False}}
        try:
            client = aioimaplib.IMAP4_SSL(account.imap_host, account.imap_port) if account.imap_ssl else aioimaplib.IMAP4(account.imap_host, account.imap_port)
            await client.wait_hello_from_server(); await client.login(account.username, decrypt(account.password_encrypted)); await client.logout(); result["imap"] = {"ok": True}
        except Exception as exc: result["imap"]["error"] = str(exc)
        try:
            smtp = aiosmtplib.SMTP(hostname=account.smtp_host, port=account.smtp_port, use_tls=account.smtp_ssl, timeout=15)
            await smtp.connect(); await smtp.login(account.smtp_username, decrypt(account.smtp_password_encrypted)); await smtp.quit(); result["smtp"] = {"ok": True}
        except Exception as exc: result["smtp"]["error"] = str(exc)
        return result
    async def send(self, account: Account, data, attachments):
        msg = EmailMessage(); msg["From"] = account.email; msg["To"] = ", ".join(data.to); msg["Cc"] = ", ".join(data.cc); msg["Subject"] = data.subject; msg.set_content(data.text or "")
        if data.html: msg.add_alternative(data.html, subtype="html")
        for filename, content_type, body in attachments:
            major, minor = content_type.split("/", 1); msg.add_attachment(body, maintype=major, subtype=minor, filename=filename)
        await aiosmtplib.send(msg, hostname=account.smtp_host, port=account.smtp_port, username=account.smtp_username, password=decrypt(account.smtp_password_encrypted), use_tls=account.smtp_ssl, recipients=[*data.to, *data.cc, *data.bcc])
    async def sync(self, db, account):
        count = 0; account_id = account.id; account_email = account.email
        try:
            client = aioimaplib.IMAP4_SSL(account.imap_host, account.imap_port) if account.imap_ssl else aioimaplib.IMAP4(account.imap_host, account.imap_port)
            await client.wait_hello_from_server(); await client.login(account.username, decrypt(account.password_encrypted))
            listed = await client.list('""', '"*"'); mailboxes = _mailboxes(listed.lines)
            if not mailboxes: mailboxes = [("INBOX", "INBOX")]
            for imap_name, folder in mailboxes:
                selected = await client.select(imap_name)
                if selected.result != "OK": continue
                # Публичный uid() aioimaplib не поддерживает SEARCH, поэтому используем
                # UID SEARCH через протокол библиотеки, сохраняя стабильные UID для дедупликации.
                search = await client.protocol.search("ALL", charset=None, by_uid=True)
                uids = [int(token) for line in search.lines if isinstance(line, bytes) for token in line.decode(errors="ignore").split() if token.isdigit()][-250:]
                existing = set((await db.scalars(select(Message.uid).where(Message.account_id == account_id, Message.folder == folder, Message.uid.in_(uids)))).all()) if uids else set()
                for uid in uids:
                    if uid in existing: continue
                    response = await client.uid("fetch", str(uid), "(BODY.PEEK[] FLAGS)")
                    raw = _message_bytes(response.lines)
                    if not raw: continue
                    metadata = b" ".join(line for line in response.lines if isinstance(line, bytes) and line is not raw)
                    db.add(_parse(raw, account_id, folder, uid, metadata))
                    try: await db.commit(); count += 1
                    except IntegrityError: await db.rollback()
            await client.logout(); await write_log(db, "sync", f"{account_email}: новых писем {count}")
        except Exception as exc:
            await db.rollback(); logger.exception("Ошибка синхронизации IMAP для %s", account_email)
            try: await write_log(db, "imap_error", f"{account_email}: {exc}", "error")
            except Exception: logger.exception("Не удалось записать ошибку синхронизации в журнал")
        return count
