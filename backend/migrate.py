"""Aplica as migrations de database/migrations em ordem (uma única vez cada).

    python migrate.py            # usa DATABASE_URL
    python migrate.py --status   # lista aplicadas/pendentes
"""
import sys
from pathlib import Path

import psycopg

from app.config import Config

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "database" / "migrations"


def apply_migrations(dsn: str, verbose: bool = True) -> list[str]:
    applied_now = []
    with psycopg.connect(dsn, autocommit=False) as conn:
        conn.execute(
            "create table if not exists public.schema_migrations "
            "(version text primary key, applied_at timestamptz not null default now())"
        )
        conn.execute("alter table public.schema_migrations enable row level security")
        done = {r[0] for r in conn.execute("select version from public.schema_migrations")}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in done:
                continue
            if verbose:
                print(f"Aplicando {path.name}...")
            conn.execute(path.read_text(encoding="utf-8"))
            conn.execute("insert into public.schema_migrations (version) values (%s)", (path.name,))
            applied_now.append(path.name)
        conn.commit()
    return applied_now


def main() -> None:
    dsn = Config.DATABASE_URL
    if not dsn:
        sys.exit("DATABASE_URL não configurada.")
    if "--status" in sys.argv:
        with psycopg.connect(dsn) as conn:
            exists = conn.execute("select to_regclass('public.schema_migrations')").fetchone()[0]
            done = {r[0] for r in conn.execute("select version from public.schema_migrations")} if exists else set()
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            print(f"[{'x' if path.name in done else ' '}] {path.name}")
        return
    applied = apply_migrations(dsn)
    print(f"{len(applied)} migration(s) aplicada(s)." if applied else "Banco já está atualizado.")


if __name__ == "__main__":
    main()
