"""Loading and saving the helper's settings, people and shortcuts.

Everything lives in one plain JSON file so a family member can read it,
email it, or copy it to another computer. Nothing here talks to the internet.
"""
from __future__ import annotations

import json
import locale
import os
import re
import secrets
import sys
from copy import deepcopy
from pathlib import Path

from . import i18n

ACTION_TYPES = {
    "open_app",      # target: path to a program, or an app name on macOS
    "open_website",  # target: https://...
    "open_link",     # target: any link or Windows app link, e.g. ms-photos:, calculator:
    "open_folder",   # target: a folder path
    "open_file",     # target: a file path (photo, document)
    "call",          # target: a call link, e.g. whatsapp://, skype:, tel:, a Zoom link
    "say",           # target: words to read out loud (e.g. a reminder)
    "remote_help",   # target: path to RustDesk / TeamViewer QuickSupport / AnyDesk
}
EMAIL_SERVICES = {"gmail", "outlook", "mailto"}
PLANS = {"free", "basic", "plus"}
AGENT_MODES = {"do", "show"}
SECRET_FIELDS = (("basic", "api_key"), ("plus", "api_key"))
MESSAGING = {"whatsapp_app", "whatsapp_web"}

DEFAULT_CONFIG: dict = {
    "person_name": "Nonno",
    "helper_name": "the family",
    "language": "en",
    "speak_replies": True,
    "email_service": "gmail",
    "messaging": "whatsapp_app",
    # How sure the helper must be before doing something without asking.
    "confidence_run": 0.78,
    # Below this, it says it didn't understand. In between, it asks "Did you mean ...?"
    "confidence_ask": 0.5,
    # "free": opens things and fills in emails/messages; they press Send.
    # "basic": the AI agent on Amazon Nova does the steps for them (very cheap).
    # "plus": the same agent on Claude, for harder tasks.
    "plan": "free",
    # "do": the agent presses buttons (always asking before sending/buying/deleting).
    # "show": the agent only tells them what to press.
    "agent_mode": "do",
    "basic": {
        "api_key": "",          # an Amazon Bedrock API key
        "region": "us-east-1",
        "model": "amazon.nova-lite-v1:0",
    },
    "plus": {
        "api_key": "",          # an Anthropic API key (or ANTHROPIC_API_KEY)
        "model": "claude-opus-5-5",
    },
    "contacts": [],
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


def secret_key(path: Path | None = None) -> str:
    """A random key that stays the same between restarts, so the window can reconnect."""
    path = path or config_dir() / "key.txt"
    if path.exists():
        key = path.read_text().strip()
        if len(key) >= 20:
            return key
    path.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_urlsafe(24)
    path.write_text(key)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


class ConfigError(ValueError):
    pass


def _words(value) -> list[str]:
    if isinstance(value, str):
        value = value.split(",")
    return [str(p).strip() for p in (value or []) if str(p).strip()]


def _clean_shortcuts(items) -> list[dict]:
    cleaned, seen = [], set()
    for i, sc in enumerate(items or []):
        if not isinstance(sc, dict):
            raise ConfigError(f"Shortcut {i + 1} is not valid.")
        name = str(sc.get("name", "")).strip()
        action = str(sc.get("action", "")).strip()
        target = str(sc.get("target", "")).strip()
        phrases = _words(sc.get("phrases"))
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
        cleaned.append({"name": name, "action": action, "target": target,
                        "phrases": phrases, "reply": str(sc.get("reply", "")).strip()})
    return cleaned


def _clean_contacts(items) -> list[dict]:
    cleaned, seen = [], set()
    for i, c in enumerate(items or []):
        if not isinstance(c, dict):
            raise ConfigError(f"Person {i + 1} is not valid.")
        name = str(c.get("name", "")).strip()
        if not name:
            raise ConfigError(f"Person {i + 1} needs a name.")
        if name.lower() in seen:
            raise ConfigError(f'Two people are both called "{name}".')
        seen.add(name.lower())
        email = str(c.get("email", "")).strip()
        if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ConfigError(f'"{email}" doesn\'t look like an email address.')
        raw_phone = str(c.get("phone", "")).strip()
        phone = re.sub(r"\D", "", raw_phone)
        if raw_phone and len(phone) < 8:
            raise ConfigError(f"{name}: the phone number needs the country code, e.g. +61 412 345 678.")
        cleaned.append({
            "name": name,
            "nicknames": _words(c.get("nicknames")),
            "email": email,
            "phone": phone,
            "call_link": str(c.get("call_link", "")).strip(),
        })
    return cleaned


def validate(cfg: dict) -> dict:
    """Return a cleaned copy of cfg, filling defaults. Raises ConfigError on bad entries."""
    out = deepcopy(DEFAULT_CONFIG)
    cfg = dict(cfg)
    old_ai = cfg.pop("ai", None)  # settings from Aiuta 0.2 and earlier
    if isinstance(old_ai, dict) and "plan" not in cfg:
        if old_ai.get("enabled"):
            cfg["plan"] = "plus"
        cfg.setdefault("plus", {"api_key": old_ai.get("api_key", ""),
                                "model": old_ai.get("model") or "claude-opus-5-5"})
    for key, value in cfg.items():
        if key in ("basic", "plus") and isinstance(value, dict):
            out[key].update({k: str(v).strip() for k, v in value.items() if k in out[key]})
        elif key in out:
            out[key] = value
    if out["plan"] not in PLANS:
        out["plan"] = "free"
    if out["agent_mode"] not in AGENT_MODES:
        out["agent_mode"] = "do"
    if out["language"] not in i18n.available():
        out["language"] = i18n.FALLBACK
    if out["email_service"] not in EMAIL_SERVICES:
        out["email_service"] = "gmail"
    if out["messaging"] not in MESSAGING:
        out["messaging"] = "whatsapp_app"
    out["shortcuts"] = _clean_shortcuts(out["shortcuts"])
    out["contacts"] = _clean_contacts(out["contacts"])
    return out


def first_run_config(lang: str = i18n.FALLBACK) -> dict:
    """What a brand-new install starts with: a few useful shortcuts in their language."""
    cfg = deepcopy(DEFAULT_CONFIG)
    cfg["language"] = lang
    cfg["shortcuts"] = deepcopy(i18n.get(lang).data.get("default_shortcuts", []))
    if not sys.platform.startswith("win"):
        # ms-photos: and calculator: only exist on Windows.
        cfg["shortcuts"] = [s for s in cfg["shortcuts"] if s["action"] != "open_link"]
    return validate(cfg)


def system_language() -> str:
    """The computer's language, if Aiuta has a translation for it."""
    names = []
    if sys.platform.startswith("win"):
        try:
            import ctypes
            lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            names.append(locale.windows_locale.get(lcid, ""))
        except Exception:
            pass
    try:
        names.append(locale.getlocale()[0] or "")
    except ValueError:
        pass
    names.append(os.environ.get("LANG", ""))
    langs = i18n.available()
    for name in names:
        low = name.lower()
        if low[:2] in langs and (len(low) == 2 or not low[2:3].isalpha()):
            return low[:2]
        for code, label in langs.items():  # Windows sometimes says "Italian_Italy"
            if low.startswith(label.lower()) or (code == "it" and low.startswith("italian")):
                return code
    return i18n.FALLBACK


def load(path: Path | None = None) -> dict:
    path = path or config_path()
    if not path.exists():
        return first_run_config(system_language())
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
