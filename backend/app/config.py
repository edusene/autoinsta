"""Configuração lida exclusivamente de variáveis de ambiente."""
import os

from dotenv import load_dotenv

load_dotenv()


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

    # Banco (Postgres do Supabase — conexão direta ou pooler em modo sessão)
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    DB_POOL_MAX_SIZE = int(os.getenv("DB_POOL_MAX_SIZE", "5"))

    # Supabase Auth (validação do JWT do usuário)
    SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
    SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")  # apenas projetos com segredo HS256 legado

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


class TestConfig(Config):
    ENV = "testing"
    DEBUG = False
    TESTING = True
    SECRET_KEY = "test-secret-key"
    DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:54329/autoinsta_test")
    SUPABASE_URL = "https://test.supabase.co"
    SUPABASE_JWT_SECRET = "test-jwt-secret-with-at-least-32-bytes!!"
    META_APP_ID = "123"
    META_APP_SECRET = "meta-test-secret"
    META_REDIRECT_URI = "http://localhost:5173/instagram/callback"
    META_VERIFY_TOKEN = "verify-me"
    META_WEBHOOK_EXTRA_SECRETS: list[str] = []
    TOKEN_ENCRYPTION_KEY = "rQf8bW3hVq6fJcV1lU2Hc0rIYk1C2bZgkq8n5c6n3oY="
    OPENAI_API_KEY = "sk-test-0000000000000000abcd"
    RATELIMIT_ENABLED = False
    EMBEDDED_WORKER = False
