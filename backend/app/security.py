import base64
import hashlib
from cryptography.fernet import Fernet
from app.config import settings

_key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode()).digest())
_cipher = Fernet(_key)
def encrypt(value: str) -> str: return _cipher.encrypt(value.encode()).decode()
def decrypt(value: str) -> str: return _cipher.decrypt(value.encode()).decode()

