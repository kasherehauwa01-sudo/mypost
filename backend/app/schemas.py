from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field

class AccountIn(BaseModel):
    name: str; email: EmailStr; username: str; password: str
    imap_host: str; imap_port: int = 993; imap_ssl: bool = True
    smtp_host: str; smtp_port: int = 465; smtp_ssl: bool = True; smtp_username: str; smtp_password: str
class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; name: str; email: EmailStr; username: str; imap_host: str; imap_port: int; imap_ssl: bool; smtp_host: str; smtp_port: int; smtp_ssl: bool; smtp_username: str; enabled: bool
class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; filename: str; content_type: str; size: int
class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; account_id: int; folder: str; subject: str; sender: str; recipients: str; cc: str; bcc: str; sent_at: datetime | None; size: int; html_body: str; text_body: str; is_read: bool; is_important: bool; attachments: list[AttachmentOut]
class BulkAction(BaseModel):
    ids: list[int] = Field(min_length=1); action: str; folder: str | None = None
class SendMail(BaseModel):
    account_id: int; to: list[EmailStr] = Field(min_length=1); cc: list[EmailStr] = []; bcc: list[EmailStr] = []; subject: str = ""; html: str = ""; text: str = ""

