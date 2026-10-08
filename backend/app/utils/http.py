from flask import request
from pydantic import BaseModel

from app.errors import AppError


def parse_body(model: type[BaseModel]) -> BaseModel:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise AppError("INVALID_JSON", "Corpo da requisição deve ser um objeto JSON.")
    return model.model_validate(data)


def pagination(default_limit: int = 25, max_limit: int = 100) -> tuple[int, int]:
    try:
        limit = int(request.args.get("limit", default_limit))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        raise AppError("VALIDATION_ERROR", "Parâmetros de paginação inválidos.")
    return max(1, min(limit, max_limit)), max(0, offset)
