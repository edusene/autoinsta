"""Processo worker: processa webhooks, retoma delays e renova tokens.

    python worker.py
"""
from app import create_app
from app.tasks.worker import run_forever

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        run_forever()
