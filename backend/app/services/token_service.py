"""Criptografia de tokens OAuth em repouso (Fernet = AES-128-CBC + HMAC-SHA256)."""
from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

from app.errors import AppError


def _fernet() -> Fernet:
    key = current_app.config["TOKEN_ENCRYPTION_KEY"]
    if not key:
        raise AppError("CONFIG_ERROR", "TOKEN_ENCRYPTION_KEY não configurada.", 500)
    return Fernet(key.encode())


def encrypt(token: str) -> str:
    return _fernet().encrypt(token.encode()).decode()


def decrypt(encrypted: str) -> str:
    try:
        return _fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken as exc:
        raise AppError("TOKEN_DECRYPT_ERROR", "Não foi possível ler o token salvo. Reconecte o Instagram.", 500) from exc
