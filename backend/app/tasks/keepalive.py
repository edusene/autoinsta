"""Keep-alive para hospedagens que hibernam por ociosidade (ex.: Render free).

A cada intervalo, faz GET na URL PÚBLICA do próprio serviço (ex.: .../health). A requisição
passa pelo balanceador da hospedagem e conta como tráfego de entrada, então o serviço não
hiberna. Ligado só quando KEEP_ALIVE_URL está definida — em VPS, deixe vazia.
"""
import logging
import threading
import time

import requests
from flask import Flask

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 30


def ping(url: str) -> bool:
    """Faz uma requisição; nunca lança exceção (falha só gera aviso no log)."""
    try:
        resp = requests.get(url, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        logger.warning("Keep-alive falhou: %s", type(exc).__name__)
        return False
    if not resp.ok:
        logger.warning("Keep-alive recebeu HTTP %s", resp.status_code)
        return False
    logger.debug("Keep-alive ok")
    return True


def start(app: Flask) -> bool:
    """Inicia a thread de keep-alive. Retorna False quando desligado."""
    url = app.config.get("KEEP_ALIVE_URL") or ""
    if not url:
        return False
    interval = app.config["KEEP_ALIVE_INTERVAL_SECONDS"]

    def loop():
        while True:
            time.sleep(interval)
            ping(url)

    threading.Thread(target=loop, name="keep-alive", daemon=True).start()
    logger.info("Keep-alive ativo (a cada %ss).", interval)
    return True
