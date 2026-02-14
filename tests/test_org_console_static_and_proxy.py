from __future__ import annotations

import json
import threading
import urllib.error
from contextlib import contextmanager
from http.server import ThreadingHTTPServer


def _start_server(handler_cls):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


@contextmanager
def _running_org_console(monkeypatch):
    from tools.org_console import app as org_console

    server = _start_server(org_console.Handler)
    monkeypatch.setattr(org_console, "HOST", "127.0.0.1")
    monkeypatch.setattr(org_console, "PORT", server.server_address[1])
    try:
        yield server
    finally:
        server.shutdown()


def test_org_console_serves_static_assets(monkeypatch):
    with _running_org_console(monkeypatch) as server:
        import urllib.request

        base = f"http://127.0.0.1:{server.server_address[1]}"
        index = urllib.request.urlopen(f"{base}/", timeout=5).read().decode("utf-8")
        css = urllib.request.urlopen(f"{base}/static/styles.css", timeout=5).read().decode("utf-8")
        js = urllib.request.urlopen(f"{base}/static/app.js", timeout=5).read().decode("utf-8")

        assert "<script src=\"/static/app.js\"></script>" in index
        assert "font-family:Arial" in css
        assert "async function loadAll()" in js


def test_org_console_proxy_error_shape(monkeypatch):
    from tools.org_console import app as org_console

    # point API_BASE to closed port to trigger proxy_request_failed
    monkeypatch.setattr(org_console, "API_BASE", "http://127.0.0.1:1/api")

    with _running_org_console(monkeypatch) as server:
        import urllib.request

        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            urllib.request.urlopen(f"{base}/proxy/organization/stats", timeout=3)
            assert False, "expected HTTPError"
        except urllib.error.HTTPError as e:
            payload = json.loads(e.read().decode("utf-8"))
            assert payload["error"] == "proxy_request_failed"
            assert payload["target"].endswith("/api/organization/stats")
