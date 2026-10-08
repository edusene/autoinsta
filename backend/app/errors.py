"""Erros da aplicação e formato padrão de resposta."""
import logging

from flask import Flask, jsonify
from pydantic import ValidationError
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Erro esperado, com código estável e mensagem segura para o usuário."""

    status_code = 400

    def __init__(self, code: str, message: str, status_code: int | None = None, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(AppError):
    def __init__(self, message: str = "Recurso não encontrado."):
        super().__init__("NOT_FOUND", message, 404)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Autenticação necessária."):
        super().__init__("UNAUTHORIZED", message, 401)


def ok(data=None, status: int = 200):
    return jsonify({"success": True, "data": data}), status


def error_body(code: str, message: str, details=None) -> dict:
    body = {"success": False, "error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return body


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(AppError)
    def handle_app_error(err: AppError):
        level = logging.WARNING if err.status_code < 500 else logging.ERROR
        logger.log(level, "AppError %s: %s", err.code, err.message)
        return jsonify(error_body(err.code, err.message, err.details)), err.status_code

    @app.errorhandler(ValidationError)
    def handle_validation_error(err: ValidationError):
        details = [
            {"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]}
            for e in err.errors(include_url=False, include_input=False)
        ]
        return jsonify(error_body("VALIDATION_ERROR", "Dados inválidos.", details)), 422

    @app.errorhandler(HTTPException)
    def handle_http_error(err: HTTPException):
        code = (err.name or "HTTP_ERROR").upper().replace(" ", "_")
        return jsonify(error_body(code, err.description or err.name)), err.code

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception):
        # Detalhes técnicos só no log do servidor; nunca stack trace para o cliente.
        logger.exception("Erro inesperado: %s", err)
        return jsonify(error_body("INTERNAL_ERROR", "Erro interno. Tente novamente.")), 500
