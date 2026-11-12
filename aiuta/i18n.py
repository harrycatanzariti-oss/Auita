"""Languages.

Every word Aiuta says or understands lives in one file per language in
aiuta/locales/ (en.json, it.json, ...). Adding a language means copying
en.json, translating it, and opening a pull request: no code changes.

Anything missing from a translation falls back to English.
"""
from __future__ import annotations

import datetime as dt
import json
from functools import lru_cache
from pathlib import Path

LOCALE_DIR = Path(__file__).resolve().parent / "locales"
FALLBACK = "en"


def available() -> dict[str, str]:
    """{"en": "English", "it": "Italiano", ...}"""
    out = {}
    for f in sorted(LOCALE_DIR.glob("*.json")):
        with open(f, encoding="utf-8") as fh:
            out[f.stem] = json.load(fh).get("name", f.stem)
    return out


def _read(lang: str) -> dict:
    with open(LOCALE_DIR / f"{lang}.json", encoding="utf-8") as fh:
        return json.load(fh)


class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


class Locale:
    def __init__(self, lang: str = FALLBACK):
        if lang not in available():
            lang = FALLBACK
        self.lang = lang
        data = _read(FALLBACK)
        if lang != FALLBACK:
            mine = _read(lang)
            for key, value in mine.items():
                if isinstance(value, dict) and key in ("text", "ui", "setup"):
                    data[key] = {**data[key], **value}
                else:
                    data[key] = value  # lists of words are per-language, never mixed
        self.data = data
        self.filler = set(data["filler"])

    def t(self, key: str, **kw) -> str:
        return self.data["text"].get(key, key).format_map(_SafeDict(kw))

    def join_or(self, items: list[str]) -> str:
        if len(items) <= 1:
            return "".join(items)
        return ", ".join(items[:-1]) + f", {self.data['text']['or']} " + items[-1]

    def time(self, now: dt.datetime) -> str:
        if self.data.get("clock") == "24h":
            return now.strftime("%H:%M")
        h = now.hour % 12 or 12
        return f"{h}:{now.minute:02d} {'AM' if now.hour < 12 else 'PM'}"

    def date(self, now: dt.datetime) -> str:
        return self.data["date_format"].format(
            weekday=self.data["days"][now.weekday()],
            day=now.day,
            month=self.data["months"][now.month - 1],
            year=now.year,
        )


@lru_cache(maxsize=16)
def get(lang: str) -> Locale:
    return Locale(lang)
