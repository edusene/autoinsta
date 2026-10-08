"""Loop do worker: busca jobs prontos e executa. Rode com `python worker.py`."""
import logging
import time
import traceback

from app import db
from app.repositories import job_repository
from app.tasks.handlers import HANDLERS
from app.tasks.queue import enqueue

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 1.0
MAINTENANCE_INTERVAL_SECONDS = 3600
TOKEN_REFRESH_INTERVAL_SECONDS = 6 * 3600


def run_one() -> bool:
    """Executa um job pronto. Retorna False quando a fila está vazia."""
    with db.connection() as conn:
        job = job_repository.claim_next(conn)
    if not job:
        return False
    handler = HANDLERS.get(job["type"])
    started = time.monotonic()
    try:
        if not handler:
            raise RuntimeError(f"Tipo de job desconhecido: {job['type']}")
        handler(job["payload"])
    except Exception as exc:  # noqa: BLE001 - falha do job não derruba o worker
        logger.error("Job %s (%s) falhou na tentativa %s: %s", job["id"], job["type"], job["attempts"], exc)
        logger.debug("%s", traceback.format_exc())
        with db.connection() as conn:
            job_repository.mark_failed(conn, job, f"{type(exc).__name__}: {exc}", retry_delay_seconds=30 * job["attempts"])
        return True
    with db.connection() as conn:
        job_repository.mark_done(conn, job["id"])
    logger.info("Job %s (%s) concluído em %.0fms", job["id"], job["type"], (time.monotonic() - started) * 1000)
    return True


def maintenance() -> None:
    with db.connection() as conn:
        requeued = job_repository.requeue_stale(conn)
        purged = job_repository.purge_old(conn)
        if not job_repository.exists_pending(conn, "refresh_tokens"):
            enqueue(conn, "refresh_tokens", {}, delay_seconds=TOKEN_REFRESH_INTERVAL_SECONDS, max_attempts=1)
    if requeued or purged:
        logger.info("Manutenção: %s jobs reenfileirados, %s removidos", requeued, purged)


def run_forever() -> None:
    logger.info("Worker iniciado.")
    last_maintenance = 0.0
    while True:
        try:
            if time.monotonic() - last_maintenance > MAINTENANCE_INTERVAL_SECONDS:
                maintenance()
                last_maintenance = time.monotonic()
            if not run_one():
                time.sleep(POLL_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            logger.info("Worker encerrado.")
            return
        except Exception:  # noqa: BLE001 - ex.: banco indisponível; tenta de novo
            logger.exception("Erro no loop do worker; nova tentativa em 5s.")
            time.sleep(5)
