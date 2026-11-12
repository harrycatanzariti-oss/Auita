"""Loading and saving the helper's settings and shortcuts.

Everything lives in one plain JSON file so a family member can read it,
email it, or copy it to another computer. Nothing here talks to the internet.
"""
from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from pathlib import Path

ACTION_TYPES = {
    "open_app",      # target: path to a program, or an app name on macOS
    "open_website",  # target: https://...
    "open_folder",   # target: a folder path
    "open_file",     # target: a file path (photo, document)
    "call",          # target: a call link, e.g. whatsapp://, facetime:, skype:, tel:
    "say",           # target: words to read out loud (e.g. a reminder)
    "remote_help",   # target: path to TeamViewer QuickSupport / RustDesk / AnyDesk
}

DEFAULT_CONFIG: dict = {
    "person_name": "Nonno",
    "helper_name": "Family",
    "language": "en",
    "speak_replies": True,
    "text_size": 28,
    # How sure the helper must be before doing something without asking.
    "confidence_run": 0.78,
    # Below this, it says it didn't understand. In between, it asks "Did you mean ...?"
    "confidence_ask": 0.5,
    "speech_model_path": "",
    "ai": {
        "enabled": False,
        "model": "claude-opus-5-5",
        # Leave empty to use the ANTHROPIC_API_KEY environment variable.
        "api_key": "",
    },
    "shortcuts": [],
}


def config_dir() -> Path:
    override = os.environ.get("AIUTA_HOME")
    if override:
        return Path(override)
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "aiuta"


def config_path() -> Path:
    return config_dir() / "config.json"


class ConfigError(ValueError):
    pass


def validate(cfg: dict) -> dict:
    """Return a cleaned copy of cfg, filling defaults. Raises ConfigError on bad shortcuts."""
    out = deepcopy(DEFAULT_CONFIG)
    for key, value in cfg.items():
        if key == "ai" and isinstance(value, dict):
            out["ai"].update(value)
        elif key in out:
            out[key] = value

    cleaned = []
    seen = set()
    for i, sc in enumerate(out.get("shortcuts") or []):
        if not isinstance(sc, dict):
            raise ConfigError(f"Shortcut {i + 1} is not valid.")
        name = str(sc.get("name", "")).strip()
        action = str(sc.get("action", "")).strip()
        target = str(sc.get("target", "")).strip()
        phrases = [str(p).strip() for p in (sc.get("phrases") or []) if str(p).strip()]
        if not name:
            raise ConfigError(f"Shortcut {i + 1} needs a name.")
        if name.lower() in seen:
            raise ConfigError(f'Two shortcuts are both called "{name}".')
        seen.add(name.lower())
        if action not in ACTION_TYPES:
            raise ConfigError(f'"{name}": unknown action "{action}".')
        if not target:
            raise ConfigError(f'"{name}" needs something to open or say.')
        if action == "open_website" and not target.lower().startswith(("http://", "https://")):
            target = "https://" + target
        if name.lower() not in [p.lower() for p in phrases]:
            phrases.insert(0, name)
        cleaned.append({
            "name": name,
            "action": action,
            "target": target,
            "phrases": phrases,
            "reply": str(sc.get("reply", "")).strip(),
        })
    out["shortcuts"] = cleaned
    return out


def load(path: Path | None = None) -> dict:
    path = path or config_path()
    if not path.exists():
        return deepcopy(DEFAULT_CONFIG)
    with open(path, encoding="utf-8") as f:
        return validate(json.load(f))


def save(cfg: dict, path: Path | None = None) -> dict:
    path = path or config_path()
    cfg = validate(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)
    return cfg
