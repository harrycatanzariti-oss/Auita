"""What Aiuta.exe runs (the Windows build packs this with PyInstaller)."""
import sys

from aiuta.launcher import main

if __name__ == "__main__":
    main("setup" if sys.argv[1:2] == ["setup"] else "")
