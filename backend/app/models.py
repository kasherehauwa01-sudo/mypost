from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base

class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120)); email: Mapped[str] = mapped_column(String(320))
    username: Mapped[str] = mapped_column(String(320)); password_encrypted: Mapped[str] = mapped_column(Text)
    imap_host: Mapped[str] = mapped_column(String(255)); imap_port: Mapped[int] = mapped_column(default=993); imap_ssl: Mapped[bool] = mapped_column(default=True)
    smtp_host: Mapped[str] = mapped_column(String(255)); smtp_port: Mapped[int] = mapped_column(default=465); smtp_ssl: Mapped[bool] = mapped_column(default=True)
    smtp_username: Mapped[str] = mapped_column(String(320)); smtp_password_encrypted: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(default=True); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Message(Base):
    __tablename__ = "messages"; __table_args__ = (UniqueConstraint("account_id", "folder", "uid"),)
    id: Mapped[int] = mapped_column(primary_key=True); account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    folder: Mapped[str] = mapped_column(String(255), index=True); uid: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[str | None] = mapped_column(String(998)); subject: Mapped[str] = mapped_column(Text, default="(без темы)")
    sender: Mapped[str] = mapped_column(Text, index=True); recipients: Mapped[str] = mapped_column(Text, default=""); cc: Mapped[str] = mapped_column(Text, default=""); bcc: Mapped[str] = mapped_column(Text, default="")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True); size: Mapped[int] = mapped_column(BigInteger, default=0)
    html_body: Mapped[str] = mapped_column(Text, default=""); text_body: Mapped[str] = mapped_column(Text, default="")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True); is_important: Mapped[bool] = mapped_column(Boolean, default=False)
    attachments: Mapped[list["Attachment"]] = relationship(back_populates="message", cascade="all, delete-orphan", lazy="selectin")

class Attachment(Base):
    __tablename__ = "attachments"
    id: Mapped[int] = mapped_column(primary_key=True); message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(Text); content_type: Mapped[str] = mapped_column(String(255)); size: Mapped[int] = mapped_column(BigInteger); content: Mapped[bytes]
    message: Mapped[Message] = relationship(back_populates="attachments")

class ActionLog(Base):
    __tablename__ = "action_logs"
    id: Mapped[int] = mapped_column(primary_key=True); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    level: Mapped[str] = mapped_column(String(20), default="info"); action: Mapped[str] = mapped_column(String(80)); details: Mapped[str] = mapped_column(Text, default="")

