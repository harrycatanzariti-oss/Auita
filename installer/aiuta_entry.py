"""What Aiuta.exe runs (the Windows build packs this with PyInstaller).

Aiuta.exe has no console, so if it ever fails to start, the reason is written
to %APPDATA%\\aiuta\\aiuta.log for the family to look at or send in.
"""
import os
import sys
import traceback
from pathlib import Path


def _log_dir() -> Path:
    if os.environ.get("AIUTA_HOME"):
        return Path(os.environ["AIUTA_HOME"])
    return Path(os.environ.get("APPDATA", Path.home())) / "aiuta"


if __name__ == "__main__":
    try:
        from aiuta.launcher import main

        main("setup" if sys.argv[1:2] == ["setup"] else "")
    except Exception:
        d = _log_dir()
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "aiuta.log", "a", encoding="utf-8") as f:
            f.write(traceback.format_exc() + "\n")
        sys.exit(1)
