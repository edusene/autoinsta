"""Substituição segura de variáveis {{caminho.da.variavel}}.

- Apenas busca por chave em dicionários (sem eval, sem atributos, sem template engine).
- Chaves iniciadas por "_" são internas e nunca são expostas.
- Variável inexistente vira string vazia.
"""
import json
import re

VARIABLE_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*)\s*\}\}")
ALIASES = {"user": "contact"}
MAX_VALUE_CHARS = 4000


def lookup(context: dict, path: str):
    parts = path.split(".")
    parts[0] = ALIASES.get(parts[0], parts[0])
    current = context
    for part in parts:
        if part.startswith("_") or not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _to_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)[:MAX_VALUE_CHARS]
    return str(value)[:MAX_VALUE_CHARS]


def render(template: str | None, context: dict) -> str:
    if not template:
        return ""
    return VARIABLE_RE.sub(lambda m: _to_text(lookup(context, m.group(1))), str(template))


def truncate_utf8(text: str, max_bytes: int) -> str:
    """Corta o texto respeitando o limite em bytes sem quebrar caracteres."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="ignore")
