import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings
from app.core.exceptions.auth import InvalidTokenError

def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        raise ValueError("Password must not exceed 72 bytes.")
    salt = bcrypt.gensalt(rounds=settings.bcrypt_cost)
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )

def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

def create_access_token(user_id: str, email: str) -> tuple[str, str]:
    jti = str(uuid.uuid4())
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_expiry_minutes
    )
    payload = {
        "sub": user_id,
        "email": email,
        "jti": jti,
        "iat": datetime.now(timezone.utc),
        "exp": expire,
    }
    token = jwt.encode(
        payload,
        settings.jwt_access_secret,
        algorithm=settings.jwt_algorithm,
    )
    return token, jti

def create_refresh_token(user_id: str) -> tuple[str, str]:
    raw_token = str(uuid.uuid4())
    token_hash = hash_token(raw_token)
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_refresh_expiry_days
    )
    payload = {
        "sub": user_id,
        "jti": raw_token,
        "iat": datetime.now(timezone.utc),
        "exp": expire,
    }
    token = jwt.encode(
        payload,
        settings.jwt_refresh_secret,
        algorithm=settings.jwt_algorithm,
    )
    return token, token_hash

def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_access_secret,
            algorithms=[settings.jwt_algorithm],
        )
        user_id: str = payload.get("sub")
        jti: str = payload.get("jti")
        if not user_id or not jti:
            raise InvalidTokenError()
        return {"user_id": user_id, "email": payload.get("email"), "jti": jti}
    except jwt.PyJWTError:
        raise InvalidTokenError()

def decode_refresh_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_refresh_secret,
            algorithms=[settings.jwt_algorithm],
        )
        user_id: str = payload.get("sub")
        raw_jti: str = payload.get("jti")
        if not user_id or not raw_jti:
            raise InvalidTokenError()
        return {"user_id": user_id, "token_hash": hash_token(raw_jti)}
    except jwt.PyJWTError:
        raise InvalidTokenError()