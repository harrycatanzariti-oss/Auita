"""Opening things on the computer: apps, websites, folders, links and calls.

Aiuta only ever opens things. It never types, clicks, sends, deletes or buys
anything on its own.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import webbrowser


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
    """Opens things. With dry_run it only records what it would open (tests, `aiuta try`)."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.log: list[tuple[str, str]] = []

    def open(self, action: str, target: str) -> None:
        """Raises if it couldn't be opened."""
        self.log.append((action, target))
        if self.dry_run or action == "say":
            return
        if action == "open_app":
            _open_app(target)
        elif action == "open_website":
            if not webbrowser.open(target, new=2):
                raise OSError("no browser")
        elif action in ("open_link", "open_folder", "open_file", "call", "remote_help"):
            _open_with_system(target)
        else:
            raise ValueError(action)
