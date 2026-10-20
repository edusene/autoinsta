"""Configuração lida exclusivamente de variáveis de ambiente.

Localmente, os valores vêm do arquivo .env na RAIZ do projeto (único para tudo).
Em produção (Render/VPS), vêm das variáveis de ambiente do serviço.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


class Config:
    ENV = os.getenv("APP_ENV", "development")
    DEBUG = ENV == "development"
    TESTING = False
    SECRET_KEY = os.getenv("SECRET_KEY", "")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # URL pública do frontend (redirects) e origens permitidas no CORS
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    CORS_ORIGINS = _list("CORS_ORIGINS", FRONTEND_URL)
    # Endereço público do serviço, usado nos links rastreados (/r/<código>). Padrão: FRONTEND_URL
    # (no deploy de serviço único, painel e API ficam no mesmo endereço).
    PUBLIC_URL = (os.getenv("PUBLIC_URL", "").strip() or FRONTEND_URL).rstrip("/")

    # Banco (Postgres do Supabase — conexão direta ou pooler em modo sessão)
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    DB_POOL_MAX_SIZE = int(os.getenv("DB_POOL_MAX_SIZE", "5"))

    # Supabase Auth (validação do JWT do usuário)
    SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
    SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")  # apenas projetos com segredo HS256 legado
    # Chave PÚBLICA (publishable/anon), entregue ao painel em /api/public-config
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

    # Exibido publicamente na Política de Privacidade (/privacy)
    PRIVACY_CONTACT_EMAIL = os.getenv("PRIVACY_CONTACT_EMAIL", "")

    # Painel compilado (frontend/dist), servido pelo próprio Flask
    FRONTEND_DIST = os.getenv("FRONTEND_DIST", str(ROOT_DIR / "frontend" / "dist"))

    # Meta / Instagram API with Instagram Login
    META_APP_ID = os.getenv("META_APP_ID", "")  # "Instagram App ID" do painel
    META_APP_SECRET = os.getenv("META_APP_SECRET", "")  # "Instagram App Secret" do painel
    META_REDIRECT_URI = os.getenv("META_REDIRECT_URI", "")
    META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "")
    META_GRAPH_API_VERSION = os.getenv("META_GRAPH_API_VERSION", "v25.0")
    # Segredos extras aceitos na assinatura X-Hub-Signature-256 (ex.: App Secret do app Meta)
    META_WEBHOOK_EXTRA_SECRETS = _list("META_WEBHOOK_EXTRA_SECRETS")

    # Criptografia dos tokens OAuth (Fernet)
    TOKEN_ENCRYPTION_KEY = os.getenv("TOKEN_ENCRYPTION_KEY", "")

    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_DEFAULT_MODEL = os.getenv("OPENAI_DEFAULT_MODEL", "gpt-6-luna")
    OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30"))

    # Rate limiting (memory:// é por processo; use redis:// em múltiplas instâncias)
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_DEFAULT = os.getenv("RATELIMIT_DEFAULT", "300 per minute")

    # Roda o loop do worker numa thread dentro do processo web. Útil em planos sem
    # background worker (ex.: Render free). Em produção prefira `python worker.py` separado.
    EMBEDDED_WORKER = _bool("EMBEDDED_WORKER", False)

    # Keep-alive (Render free): pinga a URL pública do próprio serviço para ele não hibernar.
    # Vazio = desligado (padrão). Em VPS, deixe vazio.
    KEEP_ALIVE_URL = os.getenv("KEEP_ALIVE_URL", "").strip()
    # Entre 60 s e 840 s (precisa ser menor que os 15 min de ociosidade do Render)
    KEEP_ALIVE_INTERVAL_SECONDS = min(max(int(os.getenv("KEEP_ALIVE_INTERVAL_SECONDS", "600")), 60), 840)


class TestConfig(Config):
    ENV = "testing"
    DEBUG = False
    TESTING = True
    SECRET_KEY = "test-secret-key"
    PUBLIC_URL = "https://app.example.com"
    DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:54329/autoinsta_test")
    SUPABASE_URL = "https://test.supabase.co"
    SUPABASE_JWT_SECRET = "test-jwt-secret-with-at-least-32-bytes!!"
    SUPABASE_ANON_KEY = "sb_publishable_test"
    PRIVACY_CONTACT_EMAIL = "privacidade@example.com"
    META_APP_ID = "123"
    META_APP_SECRET = "meta-test-secret"
    META_REDIRECT_URI = "http://localhost:5173/instagram/callback"
    META_VERIFY_TOKEN = "verify-me"
    META_WEBHOOK_EXTRA_SECRETS: list[str] = []
    TOKEN_ENCRYPTION_KEY = "rQf8bW3hVq6fJcV1lU2Hc0rIYk1C2bZgkq8n5c6n3oY="
    OPENAI_API_KEY = "sk-test-0000000000000000abcd"
    RATELIMIT_ENABLED = False
    EMBEDDED_WORKER = False
    KEEP_ALIVE_URL = ""
