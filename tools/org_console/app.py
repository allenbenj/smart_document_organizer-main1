#!/usr/bin/env python3
"""Standalone Organization Console.
Run: python tools/org_console/app.py
"""
from __future__ import annotations

import json
import mimetypes
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

API_BASE = "http://127.0.0.1:8000/api"
HOST, PORT = "127.0.0.1", 8010
STATIC_DIR = Path(__file__).resolve().parent / "static"


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes, ctype: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json_error(self, status: int, *, code: str, detail: str, target: str | None = None, upstream_status: int | None = None):
        body = {
            "error": code,
            "detail": detail,
        }
        if target:
            body["target"] = target
        if upstream_status is not None:
            body["upstream_status"] = upstream_status
        self._send(status, json.dumps(body).encode("utf-8"), "application/json")

    def _serve_static_file(self, rel_path: str) -> bool:
        rel_path = rel_path.lstrip("/")
        file_path = (STATIC_DIR / rel_path).resolve()
        if STATIC_DIR.resolve() not in file_path.parents and file_path != STATIC_DIR.resolve():
            self._send(404, b"not found", "text/plain")
            return True
        if not file_path.exists() or not file_path.is_file():
            self._send(404, b"not found", "text/plain")
            return True

        ctype = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        self._send(200, file_path.read_bytes(), f"{ctype}; charset=utf-8" if ctype.startswith("text/") or ctype in {"application/javascript"} else ctype)
        return True

    def _proxy_get(self, path: str) -> None:
        target = API_BASE + path[len("/proxy") :]
        try:
            with urllib.request.urlopen(target, timeout=60) as r:
                ctype = r.headers.get_content_type() or "application/json"
                return self._send(r.status, r.read(), ctype)
        except urllib.error.HTTPError as e:
            raw = e.read() or b""
            try:
                payload = json.loads(raw.decode("utf-8")) if raw else {}
                payload.setdefault("target", target)
                payload.setdefault("upstream_status", e.code)
                return self._send(e.code, json.dumps(payload).encode("utf-8"), "application/json")
            except Exception:
                return self._json_error(e.code, code="proxy_upstream_http_error", detail=(raw.decode("utf-8", errors="replace") or str(e)), target=target, upstream_status=e.code)
        except Exception as e:
            return self._json_error(500, code="proxy_request_failed", detail=str(e), target=target)

    def _proxy_post(self, path: str) -> None:
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0") or 0)) or b"{}"
        target = API_BASE + path[len("/proxy") :]
        req = urllib.request.Request(target, data=raw, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return self._send(r.status, r.read(), r.headers.get_content_type() or "application/json")
        except urllib.error.HTTPError as e:
            upstream_raw = e.read() or b""
            try:
                payload = json.loads(upstream_raw.decode("utf-8")) if upstream_raw else {}
                payload.setdefault("target", target)
                payload.setdefault("upstream_status", e.code)
                return self._send(e.code, json.dumps(payload).encode("utf-8"), "application/json")
            except Exception:
                return self._json_error(e.code, code="proxy_upstream_http_error", detail=(upstream_raw.decode("utf-8", errors="replace") or str(e)), target=target, upstream_status=e.code)
        except Exception as e:
            return self._json_error(500, code="proxy_request_failed", detail=str(e), target=target)

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        if path == "/":
            return self._serve_static_file("index.html")
        if path.startswith("/static/"):
            return self._serve_static_file(path[len("/static/") :])
        if self.path.startswith("/proxy/"):
            return self._proxy_get(self.path)
        return self._send(404, b"not found", "text/plain")

    def do_POST(self):  # noqa: N802
        if not self.path.startswith("/proxy/"):
            return self._send(404, b"not found", "text/plain")
        return self._proxy_post(self.path)


def main() -> None:
    print(f"Organization Console running at http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
