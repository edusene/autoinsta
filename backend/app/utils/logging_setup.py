"""Configuração de logs com remoção de segredos.

Mesmo que algum trecho de código registre por engano um token ou chave,
o filtro abaixo mascara os padrões mais comuns antes da gravação.
"""
import logging
import re

_SECRET_PATTERNS = [
    (re.compile(r"(access_token|client_secret|refresh_token|password)=([^&\s\"']+)", re.I), r"\1=***"),
    # "code" só como parâmetro de URL (código OAuth); "code=190" de erros da Meta continua visível
    (re.compile(r"([?&]code=)[^&\s\"']+", re.I), r"\1***"),
    (re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+", re.I), r"\1***"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}"), "sk-***"),
    (re.compile(r"\bIG[A-Za-z0-9]{20,}"), "IG***"),  # tokens do Instagram começam com "IG"
    (re.compile(r"\bEAA[A-Za-z0-9]{20,}"), "EAA***"),  # tokens do Facebook
]


def redact(text: str) -> str:
    for pattern, repl in _SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - nunca derrubar o log
            return True
        record.msg = redact(message)
        record.args = None
        return True


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    handler.addFilter(RedactingFilter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    # urllib3 em DEBUG registraria URLs com parâmetros sensíveis
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
