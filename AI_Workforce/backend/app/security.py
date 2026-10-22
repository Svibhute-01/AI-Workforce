from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from .config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(subject: str) -> str:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "exp": expires}
    secret = settings.effective_jwt_secret or "development-only-change-me"
    return jwt.encode(payload, secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    settings = get_settings()
    secret = settings.effective_jwt_secret or "development-only-change-me"
    try:
        payload = jwt.decode(token, secret, algorithms=[settings.jwt_algorithm])
        subject = payload.get("sub")
        if not subject:
            raise ValueError("Token subject is missing")
        return str(subject)
    except (JWTError, ValueError) as exc:
        raise ValueError("Invalid authentication token") from exc