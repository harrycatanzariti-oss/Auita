"""The small local web server behind Aiuta's window and the family setup page.

- "/"       the window they use: the big Talk button and the picture tiles
- "/setup"  the family setup page: people, shortcuts, language

Listening and talking happen in the window, using the speech recognition and
voices built into Microsoft Edge, so Aiuta needs no speech software of its
own. The words are sent here, and this decides what to open.

It is only reachable on this computer (127.0.0.1), never from the internet or
the home Wi-Fi, and every request must carry a secret key that only Aiuta's
own window knows, so a website can't change the settings behind their back.
"""
from __future__ import annotations

import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import actions, config, i18n
from .brain import Brain

WEB_DIR = Path(__file__).resolve().parent / "web"
MASK = "••••••••"
DEFAULT_PORT = 47610
MAX_TILES = 8


class AiutaServer:
    def __init__(self, port: int = DEFAULT_PORT, cfg_path=None, runner=None, key: str | None = None):
        self.cfg_path = cfg_path
        self.key = key or secrets.token_urlsafe(24)
        self.runner = runner or actions.Runner()
        self.lock = threading.Lock()
        self.brain = Brain(config.load(cfg_path), runner=self.runner)
        self._load_ai()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), self._handler())
        self.port = self.httpd.server_address[1]

    # ---- state -------------------------------------------------------------

    def _load_ai(self) -> None:
        self.brain.assistant = None
        cfg = self.brain.cfg
        if cfg["ai"].get("enabled"):
            try:
                from .assistant import Assistant
                self.brain.assistant = Assistant(cfg)
            except Exception as e:  # missing package or key: keep working without AI
                print("AI helper is off:", e)

    def reload(self, cfg: dict) -> None:
        with self.lock:
            self.brain = Brain(cfg, runner=self.runner)
            self._load_ai()

    def url(self, page: str = "") -> str:
        return f"http://127.0.0.1:{self.port}/{page}?key={self.key}"

    def ui_info(self) -> dict:
        cfg = self.brain.cfg
        loc = i18n.get(cfg["language"])
        tiles = [{"kind": "shortcut", "name": s["name"], "label": s["name"]}
                 for s in cfg["shortcuts"]]
        tiles += [{"kind": "contact", "name": c["name"],
                   "label": loc.data["ui"]["call_tile"].format(name=c["name"])}
                  for c in cfg["contacts"] if c["phone"] or c["call_link"]]
        return {
            "lang": loc.lang,
            "speech": loc.data["speech"],
            "person_name": cfg["person_name"],
            "helper_name": cfg["helper_name"],
            "speak_replies": cfg["speak_replies"],
            "set_up": bool(cfg["shortcuts"] or cfg["contacts"]),
            "tiles": tiles[:MAX_TILES],
            "ui": loc.data["ui"],
        }

    # ---- running -----------------------------------------------------------

    def start(self) -> None:
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def serve_forever(self) -> None:
        self.httpd.serve_forever()

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def _handler(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, code: int, body: bytes, ctype: str = "application/json"):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Referrer-Policy", "no-referrer")
                self.end_headers()
                self.wfile.write(body)

            def _json(self, code: int, obj) -> None:
                self._send(code, json.dumps(obj, ensure_ascii=False).encode())

            def _page_key_ok(self) -> bool:
                q = parse_qs(urlparse(self.path).query)
                given = (q.get("key") or [""])[0]
                return secrets.compare_digest(given, server.key)

            def _header_key_ok(self) -> bool:
                # A custom header can't be added by another website's form or link.
                return secrets.compare_digest(self.headers.get("X-Aiuta-Key", ""), server.key)

            def do_GET(self):
                path = urlparse(self.path).path
                if path == "/ping":
                    return self._json(200, {"app": "aiuta"})
                if path == "/icon.png":
                    return self._send(200, (WEB_DIR / "icon.png").read_bytes(), "image/png")
                if path in ("/", "/setup"):
                    if not self._page_key_ok():
                        return self._send(403, b"Please open Aiuta from its desktop icon.",
                                          "text/plain; charset=utf-8")
                    page = "index.html" if path == "/" else "setup.html"
                    return self._send(200, (WEB_DIR / page).read_bytes(), "text/html; charset=utf-8")
                if not self._header_key_ok():
                    return self._json(403, {"error": "not allowed"})
                if path == "/api/ui":
                    return self._json(200, server.ui_info())
                if path == "/api/config":
                    cfg = config.load(server.cfg_path)
                    if cfg["ai"].get("api_key"):
                        cfg["ai"]["api_key"] = MASK
                    loc = i18n.get(cfg["language"])
                    return self._json(200, {"config": cfg, "languages": i18n.available(),
                                            "setup": loc.data["setup"]})
                self._json(404, {})

            def do_POST(self):
                path = urlparse(self.path).path
                if not self._header_key_ok():
                    return self._json(403, {"error": "not allowed"})
                try:
                    length = min(int(self.headers.get("Content-Length", 0)), 1_000_000)
                    body = json.loads(self.rfile.read(length) or b"{}")
                except (ValueError, json.JSONDecodeError):
                    return self._json(400, {"error": "That wasn't valid."})

                if path == "/api/hear":
                    with server.lock:
                        result = server.brain.hear(str(body.get("text", ""))[:500])
                    return self._json(200, result.to_dict())

                if path == "/api/tile":
                    with server.lock:
                        brain = server.brain
                        brain.pending = None
                        if body.get("kind") == "contact":
                            result = brain.act({"intent": "call", "contact": body.get("name", "")})
                        else:
                            result = brain.run_shortcut(body.get("name", ""))
                    return self._json(200, result.to_dict())

                if path == "/api/config":
                    old = config.load(server.cfg_path)
                    if body.get("ai", {}).get("api_key") == MASK:
                        body["ai"]["api_key"] = old["ai"].get("api_key", "")
                    try:
                        cfg = config.save(body, server.cfg_path)
                    except config.ConfigError as e:
                        return self._json(400, {"error": str(e)})
                    server.reload(cfg)
                    return self._json(200, {"ok": True})

                if path == "/api/test":
                    try:
                        if body.get("kind") == "contact":
                            cfg = config.validate({**server.brain.cfg, "contacts": [body["item"]]})
                            brain = Brain(cfg, runner=server.runner)
                            how = "email" if body.get("how") == "email" else "call"
                            result = brain.act({"intent": how, "contact": cfg["contacts"][0]["name"]})
                        else:
                            cfg = config.validate({**server.brain.cfg, "shortcuts": [body["item"]]})
                            result = Brain(cfg, runner=server.runner).run_shortcut(
                                cfg["shortcuts"][0]["name"])
                    except (config.ConfigError, KeyError, IndexError, TypeError) as e:
                        return self._json(400, {"error": str(e) or "That wasn't valid."})
                    return self._json(200, result.to_dict())

                self._json(404, {})

        return Handler
