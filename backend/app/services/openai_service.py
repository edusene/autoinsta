"""Integração com a OpenAI (Responses API). Nunca chamada diretamente pelas rotas."""
import logging

from flask import current_app
from openai import APIError, BadRequestError, OpenAI

logger = logging.getLogger(__name__)

MAX_INPUT_CHARS = 8000


class OpenAIServiceError(Exception):
    pass


def is_configured() -> bool:
    return bool(current_app.config.get("OPENAI_API_KEY"))


def key_hint() -> str | None:
    key = current_app.config.get("OPENAI_API_KEY") or ""
    return f"••••{key[-4:]}" if len(key) >= 8 else None


def default_model() -> str:
    return current_app.config["OPENAI_DEFAULT_MODEL"]


def _client() -> OpenAI:
    if not is_configured():
        raise OpenAIServiceError("OpenAI não configurada no servidor (OPENAI_API_KEY).")
    return OpenAI(api_key=current_app.config["OPENAI_API_KEY"],
                  timeout=current_app.config["OPENAI_TIMEOUT_SECONDS"], max_retries=2)


def generate_text(
    *,
    model: str,
    instructions: str,
    input_text: str,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
    json_schema: dict | None = None,
) -> dict:
    """Gera texto. Envia somente as instruções e o texto renderizado do nó (minimização de dados).

    json_schema: força a resposta nesse formato (Structured Outputs, strict). O texto
    retornado é o JSON, que quem chamou deve interpretar.
    """
    params: dict = {
        "model": model,
        "instructions": instructions or None,
        "input": input_text[:MAX_INPUT_CHARS],
        "store": False,
    }
    if max_output_tokens:
        params["max_output_tokens"] = max_output_tokens
    if temperature is not None:
        params["temperature"] = temperature
    if json_schema:
        params["text"] = {"format": {"type": "json_schema", "name": "resposta", "schema": json_schema, "strict": True}}

    client = _client()
    try:
        try:
            response = client.responses.create(**params)
        except BadRequestError as exc:
            # Alguns modelos (de raciocínio) não aceitam temperature: tenta de novo sem.
            if "temperature" in params and "temperature" in str(exc).lower():
                logger.info("Modelo %s não aceita temperature; repetindo sem o parâmetro.", model)
                params.pop("temperature")
                response = client.responses.create(**params)
            else:
                raise
    except APIError as exc:
        logger.warning("Falha na OpenAI (model=%s): %s", model, type(exc).__name__)
        raise OpenAIServiceError(f"Falha na OpenAI: {getattr(exc, 'message', None) or type(exc).__name__}") from exc

    text = (response.output_text or "").strip()
    usage = getattr(response, "usage", None)
    return {
        "text": text,
        "model": getattr(response, "model", model),
        "usage": {
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
        },
    }
