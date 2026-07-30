import asyncio
import email
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
import aioimaplib
import aiosmtplib
from sqlalchemy.exc import IntegrityError
from app.models import Account, Attachment, Message
from app.repositories import write_log
from app.security import decrypt

def _text(value): return str(make_header(decode_header(value or "")))
def _parse(raw: bytes, account_id: int, folder: str, uid: int) -> Message:
    msg = email.message_from_bytes(raw)
    item = Message(account_id=account_id, folder=folder, uid=uid, message_id=msg.get("Message-ID"), subject=_text(msg.get("Subject")) or "(без темы)", sender=_text(msg.get("From")), recipients=_text(msg.get("To")), cc=_text(msg.get("Cc")), bcc=_text(msg.get("Bcc")), size=len(raw), is_read=False)
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
        count = 0
        try:
            client = aioimaplib.IMAP4_SSL(account.imap_host, account.imap_port) if account.imap_ssl else aioimaplib.IMAP4(account.imap_host, account.imap_port)
            await client.wait_hello_from_server(); await client.login(account.username, decrypt(account.password_encrypted)); await client.select("INBOX")
            search = await client.uid("search", "ALL"); uids = search.lines[0].decode().split()[-250:]
            for uid_text in uids:
                response = await client.uid("fetch", uid_text, "(RFC822)")
                raw = next((line for line in response.lines if isinstance(line, bytes) and line.startswith(b"From:")), None)
                if not raw: continue
                db.add(_parse(raw, account.id, "INBOX", int(uid_text)))
                try: await db.commit(); count += 1
                except IntegrityError: await db.rollback()
            await client.logout(); await write_log(db, "sync", f"{account.email}: новых писем {count}")
        except Exception as exc: await db.rollback(); await write_log(db, "imap_error", f"{account.email}: {exc}", "error")
        return count

