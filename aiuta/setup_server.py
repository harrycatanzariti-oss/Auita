"""The family setup page.

A small web page served only on this computer (127.0.0.1). A family member
opens it while sitting at the computer, or from far away while connected with
TeamViewer, RustDesk, AnyDesk or Chrome Remote Desktop, and adds the
shortcuts: "Email" opens Gmail, "Call Marco" starts a WhatsApp call, etc.

It is never reachable from the internet or the home network. Every request
must carry a random key that is only shown on this computer, so a website the
person visits can't change the settings behind their back.
"""
from __future__ import annotations

import json
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from urllib.parse import parse_qs, urlparse

from . import actions, config

MASK = "••••••••"


class SetupServer:
    def __init__(self, on_change=None, port: int = 0, cfg_path=None, runner=None):
        self.token = secrets.token_urlsafe(24)
        self.on_change = on_change
        self.cfg_path = cfg_path
        self.runner = runner or actions.Runner()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), self._handler())
        self.port = self.httpd.server_address[1]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/?key={self.token}"

    def start(self, open_browser: bool = True) -> None:
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        if open_browser:
            webbrowser.open(self.url, new=2)

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def _handler(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _authorised(self) -> bool:
                q = parse_qs(urlparse(self.path).query)
                given = self.headers.get("X-Aiuta-Key") or (q.get("key") or [""])[0]
                return secrets.compare_digest(given, server.token)

            def _send(self, code: int, body: bytes, ctype: str = "application/json"):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Frame-Options", "DENY")
                self.end_headers()
                self.wfile.write(body)

            def _json(self, code: int, obj) -> None:
                self._send(code, json.dumps(obj).encode())

            def do_GET(self):
                path = urlparse(self.path).path
                if not self._authorised():
                    return self._send(403, b"Open the setup page from the helper's window.",
                                      "text/plain")
                if path == "/":
                    page = resources.files("aiuta").joinpath("setup.html").read_text("utf-8")
                    return self._send(200, page.encode(), "text/html; charset=utf-8")
                if path == "/api/config":
                    cfg = config.load(server.cfg_path)
                    if cfg["ai"].get("api_key"):
                        cfg["ai"]["api_key"] = MASK
                    return self._json(200, cfg)
                self._send(404, b"{}")

            def do_POST(self):
                path = urlparse(self.path).path
                # Header-only key: a cross-site form can't set custom headers.
                if not secrets.compare_digest(self.headers.get("X-Aiuta-Key", ""), server.token):
                    return self._json(403, {"error": "not allowed"})
                try:
                    length = min(int(self.headers.get("Content-Length", 0)), 1_000_000)
                    body = json.loads(self.rfile.read(length) or b"{}")
                except (ValueError, json.JSONDecodeError):
                    return self._json(400, {"error": "That wasn't valid."})
                if path == "/api/config":
                    old = config.load(server.cfg_path)
                    if body.get("ai", {}).get("api_key") == MASK:
                        body["ai"]["api_key"] = old["ai"].get("api_key", "")
                    try:
                        cfg = config.save(body, server.cfg_path)
                    except config.ConfigError as e:
                        return self._json(400, {"error": str(e)})
                    if server.on_change:
                        server.on_change(cfg)
                    return self._json(200, {"ok": True})
                if path == "/api/test":
                    try:
                        sc = config.validate({"shortcuts": [body]})["shortcuts"][0]
                    except config.ConfigError as e:
                        return self._json(400, {"error": str(e)})
                    return self._json(200, {"reply": server.runner.run(sc)})
                self._json(404, {})

        return Handler
