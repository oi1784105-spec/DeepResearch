"""Authentication helpers: password hashing, signed access tokens, and key encryption."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

from cryptography.fernet import Fernet


DEFAULT_SECRET_KEY = "development-only-change-me"


def _secret() -> bytes:
    value = os.getenv("SECRET_KEY", DEFAULT_SECRET_KEY)
    return hashlib.sha256(value.encode("utf-8")).digest()


def validate_security_configuration(app_env: str) -> None:
    """Reject placeholder signing/encryption secrets in production deployments."""
    if app_env.strip().lower() != "production":
        return
    secret = os.getenv("SECRET_KEY", "").strip()
    if not secret or secret == DEFAULT_SECRET_KEY:
        raise RuntimeError("生产环境必须配置随机 SECRET_KEY")
    encryption_key = os.getenv("API_KEY_ENCRYPTION_KEY", "").strip()
    if not encryption_key:
        raise RuntimeError("生产环境必须配置 API_KEY_ENCRYPTION_KEY")
    try:
        Fernet(encryption_key.encode())
    except Exception as exc:
        raise RuntimeError("API_KEY_ENCRYPTION_KEY 不是有效的 Fernet 密钥") from exc


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210_000)
    return f"pbkdf2_sha256$210000${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, rounds, salt, expected = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), base64.urlsafe_b64decode(salt), int(rounds)
        )
        return hmac.compare_digest(base64.urlsafe_b64encode(digest).decode(), expected)
    except (ValueError, TypeError):
        return False


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_access_token(user_id: int, email: str, expires_seconds: int = 86_400) -> str:
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64(json.dumps({"sub": user_id, "email": email, "exp": int(time.time()) + expires_seconds}, separators=(",", ":")).encode())
    unsigned = f"{header}.{payload}"
    signature = _b64(hmac.new(_secret(), unsigned.encode(), hashlib.sha256).digest())
    return f"{unsigned}.{signature}"


def decode_access_token(token: str) -> dict[str, Any]:
    header, payload, signature = token.split(".", 2)
    unsigned = f"{header}.{payload}"
    expected = _b64(hmac.new(_secret(), unsigned.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        raise ValueError("invalid token")
    data = json.loads(_unb64(payload))
    if int(data.get("exp", 0)) < int(time.time()):
        raise ValueError("token expired")
    return data


def _fernet() -> Fernet:
    configured = os.getenv("API_KEY_ENCRYPTION_KEY", "").strip()
    if configured:
        return Fernet(configured.encode())
    derived = base64.urlsafe_b64encode(hashlib.sha256(_secret() + b":provider-key").digest())
    return Fernet(derived)


def encrypt_api_key(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_api_key(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()
