"""Fila de jobs em Postgres (tabela jobs) processada por worker.py.

Enfileirar dentro da mesma transação que grava os dados garante que o job
só exista se os dados existirem (e vice-versa).
"""
from app.repositories import job_repository


def enqueue(conn, job_type: str, payload: dict, delay_seconds: float = 0, max_attempts: int = 3) -> int:
    return job_repository.enqueue(conn, job_type, payload, delay_seconds, max_attempts)
