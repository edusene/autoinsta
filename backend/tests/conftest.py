"""Fixtures de teste.

Requer um Postgres de teste (docker compose -f docker-compose.test.yml up -d)
ou TEST_DATABASE_URL apontando para um banco DESCARTÁVEL — ele é recriado do zero.
Meta e OpenAI são sempre mockadas: nenhum teste chama serviços externos.
"""
import time
import uuid

import jwt
import psycopg
import pytest

from app import create_app, db
from app.config import TestConfig
from migrate import apply_migrations

TABLES = [
    "workflow_execution_logs", "workflow_executions", "contact_events", "contacts", "webhook_events",
    "oauth_tokens", "instagram_accounts", "workflows", "user_settings", "jobs", "profiles",
    "webhook_rejections",
]


def _reset_database(dsn: str) -> None:
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("drop schema if exists public cascade")
        conn.execute("drop schema if exists auth cascade")
        conn.execute("create schema public")
        # Simula o schema auth do Supabase
        conn.execute("create schema auth")
        conn.execute("create table auth.users (id uuid primary key, email text)")
    apply_migrations(dsn, verbose=False)


@pytest.fixture(scope="session")
def app():
    try:
        _reset_database(TestConfig.DATABASE_URL)
    except psycopg.OperationalError as exc:
        pytest.exit(f"Banco de teste indisponível ({TestConfig.DATABASE_URL}): {exc}", returncode=2)
    application = create_app(TestConfig)
    with application.app_context():
        yield application
    db.close_pool()


@pytest.fixture(autouse=True)
def clean_db(app):
    with db.connection() as conn:
        conn.execute(f"truncate {', '.join(TABLES)}, auth.users restart identity cascade")
    yield


@pytest.fixture
def client(app):
    return app.test_client()


def make_token(user_id: str, email: str = "user@example.com", expires_in: int = 3600, **overrides) -> str:
    now = int(time.time())
    claims = {
        "sub": user_id,
        "email": email,
        "aud": "authenticated",
        "role": "authenticated",
        "iss": f"{TestConfig.SUPABASE_URL}/auth/v1",
        "iat": now,
        "exp": now + expires_in,
        **overrides,
    }
    return jwt.encode(claims, TestConfig.SUPABASE_JWT_SECRET, algorithm="HS256")


class User:
    def __init__(self, client, user_id: str, email: str):
        self.client = client
        self.id = user_id
        self.email = email
        self.headers = {"Authorization": f"Bearer {make_token(user_id, email)}"}

    def get(self, url, **kw):
        return self.client.get(url, headers=self.headers, **kw)

    def post(self, url, json=None, **kw):
        return self.client.post(url, headers=self.headers, json=json if json is not None else {}, **kw)

    def put(self, url, json=None, **kw):
        return self.client.put(url, headers=self.headers, json=json, **kw)

    def delete(self, url, **kw):
        return self.client.delete(url, headers=self.headers, **kw)


def _create_user(client, email: str) -> User:
    user_id = str(uuid.uuid4())
    with db.connection() as conn:
        conn.execute("insert into auth.users (id, email) values (%s, %s)", (user_id, email))
    return User(client, user_id, email)


@pytest.fixture
def user(client):
    return _create_user(client, "alice@example.com")


@pytest.fixture
def other_user(client):
    return _create_user(client, "bob@example.com")


@pytest.fixture
def connected_account(user):
    """Conta Instagram conectada para `user`, com token criptografado."""
    from app.repositories import instagram_repository, profile_repository
    from app.services import token_service

    with db.connection() as conn:
        profile_repository.upsert(conn, user.id, user.email)
        account = instagram_repository.upsert_connected(
            conn, user.id,
            {"user_id": "17840000000000001", "username": "minhaloja", "name": "Minha Loja",
             "account_type": "BUSINESS"},
            ["instagram_business_basic", "instagram_business_manage_messages",
             "instagram_business_manage_comments"],
        )
        instagram_repository.save_token(conn, account["id"], user.id, token_service.encrypt("IGAAtesttoken123"),
                                        "2099-01-01T00:00:00Z")
        instagram_repository.set_webhook_subscribed(conn, account["id"], True)
    return account


@pytest.fixture
def meta_mock(monkeypatch):
    """Substitui as chamadas HTTP da Meta e registra o que foi enviado."""
    from app.services import meta_client

    calls: list[tuple] = []

    def record(name, result):
        def fn(*args, **kwargs):
            calls.append((name, args, kwargs))
            if isinstance(result, Exception):
                raise result
            return result(*args) if callable(result) else result
        return fn

    class Mock:
        def __init__(self):
            self.calls = calls

        def set(self, name, result):
            monkeypatch.setattr(meta_client, name, record(name, result))

        def named(self, name):
            return [c for c in calls if c[0] == name]

    mock = Mock()
    mock.set("send_text_message", {"recipient_id": "x", "message_id": "m_out_1"})
    mock.set("send_private_reply", {"recipient_id": "x", "message_id": "m_out_2"})
    mock.set("reply_to_comment", {"id": "reply_1"})
    mock.set("get_user_profile", {"name": "Cliente Teste", "username": "cliente_teste"})
    mock.set("subscribe_webhooks", {"success": True})
    return mock


@pytest.fixture
def openai_mock(monkeypatch):
    from app.services import openai_service

    calls: list[dict] = []

    def fake_generate_text(**kwargs):
        calls.append(kwargs)
        return {"text": "Olá! Nosso horário é das 9h às 18h.", "model": kwargs["model"],
                "usage": {"input_tokens": 10, "output_tokens": 12}}

    monkeypatch.setattr(openai_service, "generate_text", fake_generate_text)
    return calls
