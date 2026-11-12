"""Real screen reading on Windows (opens Notepad). Only runs when asked:

    set AIUTA_WINDOWS_UI_TEST=1 && python -m pytest tests/test_windows_desktop.py
"""
import os
import subprocess
import sys
import time

import pytest

pytestmark = pytest.mark.skipif(
    not (sys.platform.startswith("win") and os.environ.get("AIUTA_WINDOWS_UI_TEST")),
    reason="needs Windows with a desktop (set AIUTA_WINDOWS_UI_TEST=1)")


def test_reads_and_types_into_notepad():
    from aiuta.agent.desktop import WindowsDesktop

    proc = subprocess.Popen(["notepad.exe"])
    try:
        time.sleep(3)
        d = WindowsDesktop()
        screen = d.read()
        print(screen.describe())
        assert "notepad" in screen.title.lower()
        boxes = [e for e in screen.elements if e.kind in ("edit", "document")]
        if not boxes:  # Windows 11 Notepad shows its text area as a document
            boxes = [e for e in screen.elements if "text" in e.name.lower()]
        assert boxes, "no text box found"
        d.type(boxes[0], "Ciao from Aiuta")
        time.sleep(1)
        assert "Ciao from Aiuta" in d.read().describe()
    finally:
        subprocess.run(["taskkill", "/f", "/im", "notepad.exe"], capture_output=True)
