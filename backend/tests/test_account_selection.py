"""Regressão: conta antiga desconectada não pode "roubar" a tela da conta conectada."""
from app import db
from tests.test_webhooks_and_engine import IG_ACCOUNT, dm_payload, drain_jobs, post_webhook

OLD_IG = "17840000000000099"


def _add_old_disconnected_account(user_id: str) -> None:
    with db.connection() as conn:
        conn.execute(
            """insert into instagram_accounts (user_id, ig_user_id, username, status, connected_at, disconnected_at)
               values (%s, %s, 'conta_antiga', 'disconnected', now() - interval '2 hours', now() - interval '1 hour')""",
            (user_id, OLD_IG),
        )


def test_status_shows_connected_account_even_if_old_one_got_events(client, user, connected_account, meta_mock):
    _add_old_disconnected_account(user.id)
    # Evento chegando para a conta antiga (ela continua inscrita no app na Meta)
    payload = dm_payload("oi", mid="m-antiga", sender="555")
    payload["entry"][0]["id"] = OLD_IG
    post_webhook(client, payload)
    drain_jobs()

    status = user.get("/api/instagram/status").get_json()["data"]
    assert status["connected"] is True
    assert status["account"]["username"] == "minhaloja"

    with db.connection() as conn:
        old = conn.execute("select last_webhook_at from instagram_accounts where ig_user_id = %s",
                           (OLD_IG,)).fetchone()
    assert old["last_webhook_at"] is None  # conta antiga não é tocada


def test_disconnect_acts_on_connected_account(user, connected_account):
    _add_old_disconnected_account(user.id)
    with db.connection() as conn:  # simula a conta antiga com updated_at mais recente
        conn.execute("update instagram_accounts set username = username where ig_user_id = %s", (OLD_IG,))
    user.post("/api/instagram/disconnect")
    with db.connection() as conn:
        row = conn.execute("select status from instagram_accounts where ig_user_id = %s", (IG_ACCOUNT,)).fetchone()
    assert row["status"] == "disconnected"


def test_simulated_event_does_not_update_last_real_event(user, connected_account, meta_mock):
    user.post("/api/instagram/simulate", json={"kind": "message", "text": "oi"})
    drain_jobs()
    status = user.get("/api/instagram/status").get_json()["data"]
    assert status["account"]["last_webhook_at"] is None
