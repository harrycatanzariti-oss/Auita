"""Work out which shortcut someone meant from what they said.

Speech recognition is imperfect and people say things many ways ("open my
email", "can you show me the emails please", "e-mail"), so we strip filler
words and compare fuzzily. No AI, no internet: this runs on any old computer.
The filler words and built-in phrases come from the language file.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from .i18n import Locale


def normalize(text: str) -> str:
    text = text.lower().replace("e-mail", "email").replace("’", "'")
    text = re.sub(r"[^\w' ]+", " ", text)
    text = text.replace("_", " ")
    return re.sub(r"\s+", " ", text).strip()


def core_words(text: str, filler: set[str]) -> list[str]:
    words = normalize(text).split()
    kept = [w for w in words if w not in filler]
    return kept or words


def _singular(w: str) -> str:
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w


def similarity(said: str, phrase: str, filler: set[str]) -> float:
    a = core_words(said, filler)
    b = core_words(phrase, filler)
    if not a or not b:
        return 0.0
    sa, sb = " ".join(map(_singular, a)), " ".join(map(_singular, b))
    if sa == sb:
        return 1.0
    whole = SequenceMatcher(None, sa, sb).ratio()
    # Every word of the phrase appears (fuzzily) in what was said.
    hits = 0.0
    for wb in map(_singular, b):
        hits += max(SequenceMatcher(None, wb, _singular(wa)).ratio() for wa in a)
    coverage = hits / len(b)
    # Penalise long rambles that only mention the phrase in passing, but gently.
    extra = max(0, len(a) - len(b))
    coverage -= min(0.15, 0.03 * extra)
    return max(whole, coverage)


@dataclass
class Match:
    kind: str          # "shortcut", "builtin" or "none"
    name: str = ""
    score: float = 0.0
    shortcut: dict | None = None


def best_match(said: str, shortcuts: list[dict], loc: Locale) -> Match:
    best = Match("none")
    norm = normalize(said)
    for name, phrases in loc.data["builtins"].items():
        if name in ("yes", "no"):
            continue  # only meaningful when answering a question
        for p in phrases:
            s = 1.0 if norm == normalize(p) else similarity(said, p, loc.filler) * 0.95
            if s > best.score:
                best = Match("builtin", name, s)
    for sc in shortcuts:
        for p in sc.get("phrases") or [sc["name"]]:
            s = similarity(said, p, loc.filler)
            if s > best.score:
                best = Match("shortcut", sc["name"], s, sc)
    return best


def yes_or_no(said: str, loc: Locale) -> str | None:
    norm = normalize(said)
    scores = {}
    for name in ("yes", "no"):
        scores[name] = max(
            1.0 if norm == normalize(p) else similarity(said, p, loc.filler)
            for p in loc.data["builtins"][name]
        )
    top = max(scores, key=scores.get)
    return top if scores[top] >= 0.75 else None
