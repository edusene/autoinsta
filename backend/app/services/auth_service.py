"""Validação dos JWTs emitidos pelo Supabase Auth.

O frontend faz cadastro/login/refresh com o SDK oficial do Supabase e envia o
access token no header Authorization. Aqui validamos assinatura, expiração,
audience e issuer. Suporta:
  - chaves assimétricas (ES256/RS256) via JWKS — padrão dos projetos atuais;
  - segredo HS256 legado (SUPABASE_JWT_SECRET).
"""
import logging
from dataclasses import dataclass
from functools import lru_cache

import jwt
from flask import current_app

from app.errors import UnauthorizedError
from app.repositories import profile_repository
from app import db

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str | None


@lru_cache(maxsize=4)
def _jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)


def verify_token(token: str) -> AuthUser:
    cfg = current_app.config
    issuer = f"{cfg['SUPABASE_URL']}/auth/v1"
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg")
        if alg == "HS256":
            if not cfg["SUPABASE_JWT_SECRET"]:
                raise UnauthorizedError("Configuração de autenticação inválida.")
            key = cfg["SUPABASE_JWT_SECRET"]
        elif alg in ("ES256", "RS256"):
            key = _jwks_client(f"{issuer}/.well-known/jwks.json").get_signing_key_from_jwt(token).key
        else:
            raise UnauthorizedError("Token inválido.")
        claims = jwt.decode(
            token,
            key,
            algorithms=[alg],
            audience="authenticated",
            issuer=issuer,
            options={"require": ["exp", "sub"]},
        )
    except UnauthorizedError:
        raise
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Sessão expirada. Faça login novamente.")
    except (jwt.PyJWTError, ValueError) as exc:
        logger.info("JWT rejeitado: %s", type(exc).__name__)
        raise UnauthorizedError("Token inválido.")

    if claims.get("role") != "authenticated":
        raise UnauthorizedError("Token inválido.")
    return AuthUser(id=claims["sub"], email=claims.get("email"))


def ensure_profile(user: AuthUser) -> dict:
    """Cria o perfil no primeiro acesso (o usuário já existe em auth.users)."""
    with db.connection() as conn:
        return profile_repository.upsert(conn, user.id, user.email)


def get_profile(user_id: str) -> dict | None:
    with db.connection() as conn:
        return profile_repository.get(conn, user_id)
