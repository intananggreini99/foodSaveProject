"""Password di-hash scrypt; token sesi hanya disimpan sebagai SHA-256."""

import hashlib
import hmac
import secrets
from datetime import datetime, timezone

COOKIE = "foodsave_session"
DUMMY_HASH = "scrypt$" + "00" * 16 + "$" + "00" * 64


def now() -> datetime:
    return datetime.now(timezone.utc)


def password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f"scrypt${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        candidate = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1
        ).hex()
        return hmac.compare_digest(candidate, digest)
    except (ValueError, TypeError):
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
