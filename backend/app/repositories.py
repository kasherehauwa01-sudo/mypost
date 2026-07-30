from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models import Account, ActionLog, Attachment, Message

class AccountRepository:
    def __init__(self, db: AsyncSession): self.db = db
    async def list(self): return list((await self.db.scalars(select(Account).order_by(Account.name))).all())
    async def get(self, account_id: int): return await self.db.get(Account, account_id)
    async def add(self, account: Account): self.db.add(account); await self.db.commit(); await self.db.refresh(account); return account
    async def delete(self, account_id: int): await self.db.execute(delete(Account).where(Account.id == account_id)); await self.db.commit()

class MessageRepository:
    def __init__(self, db: AsyncSession): self.db = db
    async def list(self, folder=None, query=None, sender=None, unread=None, important=None, has_attachment=None, min_size=None, max_size=None, limit=100, offset=0):
        stmt = select(Message).order_by(Message.sent_at.desc().nullslast()).limit(limit).offset(offset)
        if folder: stmt = stmt.where(Message.folder == folder)
        if sender: stmt = stmt.where(Message.sender.ilike(f"%{sender}%"))
        if unread is not None: stmt = stmt.where(Message.is_read == (not unread))
        if important is not None: stmt = stmt.where(Message.is_important == important)
        if min_size is not None: stmt = stmt.where(Message.size >= min_size)
        if max_size is not None: stmt = stmt.where(Message.size <= max_size)
        if has_attachment is not None: stmt = stmt.where(Message.attachments.any() if has_attachment else ~Message.attachments.any())
        if query: stmt = stmt.where(or_(Message.subject.ilike(f"%{query}%"), Message.sender.ilike(f"%{query}%"), Message.text_body.ilike(f"%{query}%"), Message.attachments.any(Attachment.filename.ilike(f"%{query}%"))))
        return list((await self.db.scalars(stmt)).unique().all())
    async def get(self, message_id): return await self.db.get(Message, message_id)
    async def attachments(self): return list((await self.db.scalars(select(Attachment).join(Message).options(selectinload(Attachment.message)).order_by(Message.sent_at.desc()))).all())
    async def bulk(self, ids, action, folder=None):
        messages = list((await self.db.scalars(select(Message).where(Message.id.in_(ids)))).all())
        if action == "delete":
            for item in messages: await self.db.delete(item)
        else:
            for item in messages:
                if action == "read": item.is_read = True
                elif action == "unread": item.is_read = False
                elif action == "important": item.is_important = True
                elif action == "move" and folder: item.folder = folder
                elif action == "trash": item.folder = "Trash"
        await self.db.commit(); return len(messages)
    async def stats(self):
        total, unread, size = (await self.db.execute(select(func.count(Message.id), func.count(Message.id).filter(~Message.is_read), func.coalesce(func.sum(Message.size), 0)))).one()
        acount, asize = (await self.db.execute(select(func.count(Attachment.id), func.coalesce(func.sum(Attachment.size), 0)))).one()
        top = (await self.db.execute(select(Message.sender, func.count()).group_by(Message.sender).order_by(func.count().desc()).limit(10))).all()
        return {"total_messages": total, "unread": unread, "message_bytes": size, "attachments": acount, "attachment_bytes": asize, "top_senders": [{"sender": x, "count": y} for x,y in top]}

async def write_log(db, action, details="", level="info"):
    db.add(ActionLog(action=action, details=details, level=level)); await db.commit()
