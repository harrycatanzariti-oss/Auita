"""Doing things on the computer: opening apps, websites, folders and calls.

Only the shortcuts a family member set up can run. The helper never types,
clicks, deletes or buys anything on its own.
"""
from __future__ import annotations

import datetime as dt
import os
import shutil
import subprocess
import sys
import webbrowser
from typing import Callable

Opener = Callable[[str], None]


def _open_with_system(target: str) -> None:
    if sys.platform.startswith("win"):
        os.startfile(target)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", target])
    else:
        subprocess.Popen(["xdg-open", target])


def _open_app(target: str) -> None:
    if sys.platform == "darwin" and not os.path.exists(target):
        subprocess.Popen(["open", "-a", target])  # e.g. "Mail", "Photos"
        return
    if os.path.exists(target):
        if sys.platform.startswith("win") or sys.platform == "darwin":
            _open_with_system(target)
        else:
            subprocess.Popen([target])
        return
    found = shutil.which(target)
    if found:
        subprocess.Popen([found])
        return
    raise FileNotFoundError(target)


class Runner:
    """Runs a shortcut. `dry_run` records what would happen (used by tests and the setup page)."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.log: list[tuple[str, str]] = []

    def run(self, shortcut: dict) -> str:
        action, target = shortcut["action"], shortcut["target"]
        name = shortcut["name"]
        reply = shortcut.get("reply") or ""
        self.log.append((action, target))

        if action == "say":
            return target

        if not self.dry_run:
            try:
                if action == "open_app":
                    _open_app(target)
                elif action == "open_website":
                    webbrowser.open(target, new=2)
                elif action in ("open_folder", "open_file", "call", "remote_help"):
                    _open_with_system(target)
                else:
                    return f"I don't know how to do {name} yet."
            except Exception:
                return f"Sorry, I couldn't open {name}. Ask the family to check it."

        if reply:
            return reply
        if action == "call":
            return f"Calling {name}."
        if action == "remote_help":
            return "Opening help. Tell the family the number on the screen."
        return f"Opening {name}."


def builtin_reply(name: str, cfg: dict, now: dt.datetime | None = None) -> str:
    now = now or dt.datetime.now()
    if name == "time":
        return "It's " + now.strftime("%I:%M %p").lstrip("0") + "."
    if name == "date":
        return "Today is " + now.strftime("%A, %d %B %Y").replace(" 0", " ") + "."
    if name == "list":
        names = [s["name"] for s in cfg.get("shortcuts", [])]
        if not names:
            return "Nothing is set up yet. Ask the family to add some shortcuts."
        if len(names) == 1:
            return f"You can say: {names[0]}."
        return "You can say: " + ", ".join(names[:-1]) + ", or " + names[-1] + "."
    return ""
