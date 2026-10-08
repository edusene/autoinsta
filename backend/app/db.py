"""Acesso ao Postgres com psycopg 3 + pool.

Uso:
    with db.connection() as conn:
        row = conn.execute("select ... where id = %s", (id,)).fetchone()

O bloco faz commit ao sair sem erro e rollback em caso de exceção.
Sempre use parâmetros (%s) — nunca concatene valores em SQL.
"""
from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None

__all__ = ["init_pool", "close_pool", "connection", "Jsonb"]


def init_pool(dsn: str, max_size: int = 5) -> None:
    global _pool
    if _pool is not None:
        return
    if not dsn:
        raise RuntimeError("DATABASE_URL não configurada.")
    # prepare_threshold=None: compatível com poolers em modo transação (Supavisor/PgBouncer)
    _pool = ConnectionPool(
        dsn,
        min_size=1,
        max_size=max_size,
        kwargs={"row_factory": dict_row, "prepare_threshold": None},
        open=True,
    )


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def connection():
    if _pool is None:
        raise RuntimeError("Pool de banco não inicializado.")
    with _pool.connection() as conn:
        yield conn
