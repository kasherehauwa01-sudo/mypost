import json
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import SessionLocal, get_db
from app.mail_service import MailService
from app.models import Account, ActionLog, Attachment, Message
from app.repositories import AccountRepository, MessageRepository, write_log
from app.schemas import AccountIn, AccountOut, AccountUpdate, BulkAction, MessageOut, SendMail
from app.security import encrypt

router = APIRouter(); mail = MailService()
async def sync_account_in_background(account_id: int) -> None:
    """Запускает долгую IMAP-синхронизацию вне HTTP-запроса."""
    async with SessionLocal() as db:
        account = await AccountRepository(db).get(account_id)
        if account: await mail.sync(db, account)
@router.get("/accounts", response_model=list[AccountOut])
async def accounts(db: AsyncSession = Depends(get_db)): return await AccountRepository(db).list()
@router.post("/accounts", response_model=AccountOut, status_code=201)
async def add_account(data: AccountIn, db: AsyncSession = Depends(get_db)):
    values = data.model_dump(exclude={"password", "smtp_password"}); values.update(password_encrypted=encrypt(data.password), smtp_password_encrypted=encrypt(data.smtp_password))
    return await AccountRepository(db).add(Account(**values))
@router.put("/accounts/{account_id}", response_model=AccountOut)
async def update_account(account_id: int, data: AccountUpdate, db: AsyncSession = Depends(get_db)):
    repository = AccountRepository(db); account = await repository.get(account_id)
    if not account: raise HTTPException(404, "Аккаунт не найден")
    values = data.model_dump(exclude={"password", "smtp_password"})
    if data.password: values["password_encrypted"] = encrypt(data.password)
    if data.smtp_password: values["smtp_password_encrypted"] = encrypt(data.smtp_password)
    return await repository.update(account, values)
@router.delete("/accounts/{account_id}", status_code=204)
async def remove_account(account_id: int, db: AsyncSession = Depends(get_db)):
    repository = AccountRepository(db)
    if not await repository.get(account_id): raise HTTPException(404, "Аккаунт не найден")
    await repository.delete(account_id)
@router.post("/accounts/{account_id}/check")
async def check(account_id: int, db: AsyncSession = Depends(get_db)):
    account = await AccountRepository(db).get(account_id)
    if not account: raise HTTPException(404, "Аккаунт не найден")
    result = await mail.check(account); await write_log(db, "connection_check", json.dumps(result, ensure_ascii=False)); return result
@router.post("/accounts/{account_id}/sync", status_code=202)
async def sync(account_id: int, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    account = await AccountRepository(db).get(account_id)
    if not account: raise HTTPException(404, "Аккаунт не найден")
    background_tasks.add_task(sync_account_in_background, account_id)
    return {"status": "queued"}

@router.get("/messages", response_model=list[MessageOut])
async def messages(folder: str | None = None, q: str | None = None, sender: str | None = None, unread: bool | None = None, important: bool | None = None, has_attachment: bool | None = None, min_size: int | None = None, max_size: int | None = None, limit: int = 100, offset: int = 0, db: AsyncSession = Depends(get_db)):
    return await MessageRepository(db).list(folder, q, sender, unread, important, has_attachment, min_size, max_size, min(limit, 250), offset)
@router.get("/folders", response_model=list[str])
async def folders(db: AsyncSession = Depends(get_db)):
    return list((await db.scalars(select(Message.folder).distinct().order_by(Message.folder))).all())
@router.get("/messages/{message_id}", response_model=MessageOut)
async def message(message_id: int, db: AsyncSession = Depends(get_db)):
    item = await MessageRepository(db).get(message_id)
    if not item: raise HTTPException(404, "Письмо не найдено")
    return item
@router.post("/messages/bulk")
async def bulk(data: BulkAction, db: AsyncSession = Depends(get_db)):
    if data.action not in {"delete", "trash", "move", "read", "unread", "important"}: raise HTTPException(400, "Неизвестная операция")
    count = await MessageRepository(db).bulk(data.ids, data.action, data.folder); await write_log(db, data.action, f"Писем: {count}"); return {"affected": count}
@router.delete("/trash")
async def empty_trash(db: AsyncSession = Depends(get_db)):
    result = await db.execute(delete(Message).where(Message.folder == "Trash")); await db.commit(); await write_log(db, "empty_trash", f"Писем: {result.rowcount}"); return {"deleted": result.rowcount}

@router.post("/send")
async def send(payload: str = Form(...), files: list[UploadFile] = File(default=[]), db: AsyncSession = Depends(get_db)):
    data = SendMail.model_validate_json(payload); account = await AccountRepository(db).get(data.account_id)
    if not account: raise HTTPException(404, "Аккаунт не найден")
    try:
        uploads = [(f.filename or "file", f.content_type or "application/octet-stream", await f.read()) for f in files]
        await mail.send(account, data, uploads); await write_log(db, "send", f"{account.email}: {data.subject}"); return {"sent": True}
    except Exception as exc: await write_log(db, "smtp_error", str(exc), "error"); raise HTTPException(502, f"Ошибка SMTP: {exc}")
@router.get("/attachments")
async def attachments(db: AsyncSession = Depends(get_db)):
    items = await MessageRepository(db).attachments()
    return [{"id": x.id, "filename": x.filename, "content_type": x.content_type, "size": x.size, "sender": x.message.sender, "date": x.message.sent_at, "folder": x.message.folder} for x in items]
@router.get("/attachments/{attachment_id}/download")
async def download(attachment_id: int, db: AsyncSession = Depends(get_db)):
    item = await db.get(Attachment, attachment_id)
    if not item: raise HTTPException(404, "Вложение не найдено")
    return Response(item.content, media_type=item.content_type, headers={"Content-Disposition": f'attachment; filename="{item.filename}"'})
@router.get("/stats")
async def stats(db: AsyncSession = Depends(get_db)): return await MessageRepository(db).stats()
@router.get("/logs")
async def logs(db: AsyncSession = Depends(get_db)):
    items = list((await db.scalars(select(ActionLog).order_by(ActionLog.created_at.desc()).limit(500))).all())
    return [{"id": x.id, "created_at": x.created_at, "level": x.level, "action": x.action, "details": x.details} for x in items]
