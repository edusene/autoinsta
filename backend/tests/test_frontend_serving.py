import pytest


@pytest.fixture
def dist(app, tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>painel</html>", encoding="utf-8")
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path.parent / "segredo.txt").write_text("nao pode vazar", encoding="utf-8")
    original = app.config["FRONTEND_DIST"]
    app.config["FRONTEND_DIST"] = str(tmp_path)
    yield tmp_path
    app.config["FRONTEND_DIST"] = original


def test_public_config_exposes_only_public_values(client):
    data = client.get("/api/public-config").get_json()["data"]
    assert data == {"supabase_url": "https://test.supabase.co", "supabase_anon_key": "sb_publishable_test",
                    "privacy_contact_email": "privacidade@example.com"}


def test_serves_index_and_spa_routes(client, dist):
    for path in ("/", "/dashboard", "/privacy", "/workflows/123", "/instagram/callback?code=x&state=y"):
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert b"painel" in resp.data
        assert resp.headers["Cache-Control"] == "no-cache"


def test_serves_hashed_assets_with_long_cache(client, dist):
    resp = client.get("/assets/index-abc123.js")
    assert resp.status_code == 200 and b"console.log" in resp.data
    assert "immutable" in resp.headers["Cache-Control"]


def test_path_traversal_blocked(client, dist):
    for path in ("/../segredo.txt", "/assets/../../segredo.txt", "/%2e%2e/segredo.txt"):
        assert b"nao pode vazar" not in client.get(path).data


def test_api_routes_are_not_swallowed_by_spa(client, dist, user):
    resp = client.get("/api/nao-existe")
    assert resp.status_code == 404 and resp.get_json()["success"] is False
    assert user.get("/api/workflows").status_code == 200
    assert client.get("/health").get_json()["database"] == "ok"
    assert client.get("/webhooks/meta?hub.mode=subscribe&hub.verify_token=verify-me&hub.challenge=7").data == b"7"


def test_missing_build_returns_clear_404(client, app, tmp_path):
    original = app.config["FRONTEND_DIST"]
    app.config["FRONTEND_DIST"] = str(tmp_path / "nao-existe")
    try:
        resp = client.get("/dashboard")
        assert resp.status_code == 404
        assert "npm run build" in resp.get_json()["error"]["message"]
    finally:
        app.config["FRONTEND_DIST"] = original
