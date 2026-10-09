import requests

from app.tasks import keepalive


class _Resp:
    def __init__(self, ok, status=200):
        self.ok, self.status_code = ok, status


def test_ping_success(monkeypatch):
    monkeypatch.setattr(keepalive.requests, "get", lambda url, timeout: _Resp(True))
    assert keepalive.ping("https://exemplo/health") is True


def test_ping_http_error_and_network_error_never_raise(monkeypatch):
    monkeypatch.setattr(keepalive.requests, "get", lambda url, timeout: _Resp(False, 503))
    assert keepalive.ping("https://exemplo/health") is False

    def boom(url, timeout):
        raise requests.Timeout()

    monkeypatch.setattr(keepalive.requests, "get", boom)
    assert keepalive.ping("https://exemplo/health") is False


def test_start_disabled_without_url(app):
    assert app.config["KEEP_ALIVE_URL"] == ""
    assert keepalive.start(app) is False


def test_start_enabled_with_url(app, monkeypatch):
    started = []
    monkeypatch.setattr(keepalive.threading, "Thread", lambda **kw: type("T", (), {"start": lambda self: started.append(kw["name"])})())
    monkeypatch.setitem(app.config, "KEEP_ALIVE_URL", "https://exemplo/health")
    assert keepalive.start(app) is True
    assert started == ["keep-alive"]
