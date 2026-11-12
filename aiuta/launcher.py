"""Starting Aiuta: what the desktop icon runs.

1. If Aiuta is already running, just open its window again.
2. Otherwise start the local server and open the window.

The window is Microsoft Edge in "app mode": no address bar, no tabs, it
looks like a normal program. Edge is already on every Windows 10 and 11
computer and brings free speech recognition and natural voices in every
major language, so Aiuta doesn't need its own. Aiuta uses its own Edge
profile, so their normal browsing, passwords and tabs are never touched.
If Edge is missing it falls back to Chrome, then to the default browser.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.request
import webbrowser
from pathlib import Path

from . import config
from .server import DEFAULT_PORT, AiutaServer

WINDOW_SIZE = "960,860"


def find_browser() -> str | None:
    candidates = []
    if sys.platform.startswith("win"):
        for env in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
            base = os.environ.get(env)
            if base:
                candidates.append(Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
        for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            base = os.environ.get(env)
            if base:
                candidates.append(Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe")
    elif sys.platform == "darwin":
        candidates += [Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
                       Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")]
    for c in candidates:
        if c.exists():
            return str(c)
    for name in ("msedge", "microsoft-edge", "google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    return None


def window_command(browser: str, url: str, profile: Path) -> list[str]:
    return [
        browser,
        f"--app={url}",
        f"--user-data-dir={profile}",
        f"--window-size={WINDOW_SIZE}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=Translate",
    ]


def open_window(url: str) -> None:
    if os.environ.get("AIUTA_NO_WINDOW"):  # used by the automatic build check
        return
    browser = find_browser()
    if browser:
        profile = config.config_dir() / "window"
        profile.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(window_command(browser, url, profile))
    else:
        webbrowser.open(url, new=1)


def already_running(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/ping", timeout=1.5) as r:
            return json.load(r).get("app") == "aiuta"
    except Exception:
        return False


def main(page: str = "") -> None:
    key = config.secret_key()
    port = int(os.environ.get("AIUTA_PORT", DEFAULT_PORT))
    if already_running(port):
        open_window(f"http://127.0.0.1:{port}/{page}?key={key}")
        return
    try:
        server = AiutaServer(port=port, key=key)
    except OSError:
        # Something else has the port: use any free one for this session.
        server = AiutaServer(port=0, key=key)
    open_window(server.url(page))
    try:
        server.serve_forever()  # keeps running quietly; the icon re-opens the window
    except KeyboardInterrupt:
        server.stop()
