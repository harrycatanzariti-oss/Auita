"""Work out which shortcut someone meant from what they said.

Speech recognition is imperfect and people say things many ways ("open my
email", "can you show me the emails please", "e-mail"), so we strip filler
words and compare fuzzily. No AI, no internet: this runs on any old computer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

FILLER = {
    "please", "can", "could", "would", "you", "i", "want", "to", "wanna", "like",
    "open", "show", "me", "my", "the", "a", "an", "go", "take", "start", "put",
    "on", "up", "get", "bring", "launch", "run", "let", "lets", "let's", "do",
    "now", "for", "into", "in", "of", "just", "help", "need", "some", "pull",
    "turn", "load", "find", "see", "look", "at", "is", "there", "where",
    "hey", "ok", "okay", "um", "uh", "so", "and", "then", "thanks", "thank",
}

BUILTINS = {
    "list": ["what can i say", "what can you do", "help me", "options", "list",
             "what are my options", "help"],
    "time": ["what time is it", "time", "what's the time", "tell me the time"],
    "date": ["what day is it", "what's the date", "date", "today's date", "what is today"],
    "yes": ["yes", "yeah", "yep", "correct", "that's right", "si", "sì", "ok do it"],
    "no": ["no", "nope", "wrong", "not that", "cancel", "stop", "never mind"],
}


def normalize(text: str) -> str:
    text = text.lower().replace("e-mail", "email").replace("’", "'")
    text = re.sub(r"[^a-z0-9à-ÿ' ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def core_words(text: str) -> list[str]:
    words = normalize(text).split()
    kept = [w for w in words if w not in FILLER]
    return kept or words


def _singular(w: str) -> str:
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w


def similarity(said: str, phrase: str) -> float:
    a = core_words(said)
    b = core_words(phrase)
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


def best_match(said: str, shortcuts: list[dict], include_builtins: bool = True) -> Match:
    best = Match("none")
    if include_builtins:
        for name, phrases in BUILTINS.items():
            if name in ("yes", "no"):
                continue  # only meaningful when answering a question
            for p in phrases:
                s = 1.0 if normalize(said) == normalize(p) else similarity(said, p) * 0.95
                if s > best.score:
                    best = Match("builtin", name, s)
    for sc in shortcuts:
        for p in sc.get("phrases") or [sc["name"]]:
            s = similarity(said, p)
            if s > best.score:
                best = Match("shortcut", sc["name"], s, sc)
    return best


def yes_or_no(said: str) -> str | None:
    norm = normalize(said)
    scores = {}
    for name in ("yes", "no"):
        scores[name] = max(
            1.0 if norm == normalize(p) else similarity(said, p) for p in BUILTINS[name]
        )
    top = max(scores, key=scores.get)
    return top if scores[top] >= 0.75 else None
