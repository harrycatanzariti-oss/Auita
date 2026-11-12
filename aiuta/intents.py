"""Requests with something in them: who to email, what to search for.

"Email Mary about Sunday lunch"      -> a new email to Mary, subject "Sunday lunch"
"Can you search for cheap flights"   -> Google search for "cheap flights"
"Play Pavarotti on YouTube"          -> YouTube results for "Pavarotti"
"How do I get to the hospital"       -> the map, with directions there
"Call Mary" / "Message Mary"         -> WhatsApp (or their call link), on Mary

"Email Mary saying I'll be late"     -> the same, with "I'll be late" already written in

On the free plan Aiuta only takes them to the right screen, with the words
filled in. It never sends, posts or calls on its own: they press Send.

The words and patterns come from the language file, so this works in any
language that has one.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from functools import lru_cache
from urllib.parse import quote, urlencode

from .i18n import Locale
from .matcher import normalize


@lru_cache(maxsize=256)
def _compile(pattern: str) -> re.Pattern:
    if "{q}" in pattern:
        body = pattern.replace("{q}", "(?P<q>.+)")
        return re.compile(r"(?:^|(?<=\s))" + body + r"$")
    return re.compile(r"(?:^|(?<=\s))" + pattern + r"(?=\s|$)")


def _strip_trailing(text: str, loc: Locale) -> str:
    changed = True
    while changed and text:
        changed = False
        for t in sorted(loc.data.get("trailing_filler", []), key=len, reverse=True):
            t = normalize(t)
            if text == t:
                return text
            if text.endswith(" " + t):
                text = text[: -len(t) - 1].strip()
                changed = True
    return text


def _clean_query(q: str, loc: Locale) -> str:
    words = q.split()
    lead = set(loc.data.get("q_strip", []))
    while len(words) > 1 and words[0] in lead:
        words.pop(0)
    return " ".join(words).strip()


def find_contact(norm: str, contacts: list[dict]) -> tuple[dict | None, float]:
    best, best_score = None, 0.0
    words = norm.split()
    for c in contacts:
        for alias in [c["name"], *c.get("nicknames", [])]:
            a = normalize(alias)
            if not a:
                continue
            if re.search(r"(?:^|\s)" + re.escape(a) + r"(?:'s)?(?=\s|$)", norm):
                score = 1.0 + len(a) / 1000  # prefer "mary ann" over "mary"
            else:
                n = len(a.split())
                grams = [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]
                score = max((SequenceMatcher(None, a, g).ratio() for g in grams), default=0.0)
                if score < 0.8 or len(a) < 3:
                    score = 0.0
            if score > best_score:
                best, best_score = c, score
    return best, best_score


def _first_keyword(norm: str, keywords: list[str]) -> int:
    pos = -1
    for kw in keywords:
        m = re.search(r"(?:^|\s)" + re.escape(normalize(kw)) + r"(?=\s|$)", norm)
        if m and (pos < 0 or m.start() < pos):
            pos = m.start()
    return pos


def _after(norm: str, words: list[str], loc: Locale) -> str:
    for w in sorted(words, key=len, reverse=True):
        m = re.search(r"(?:^|\s)" + re.escape(normalize(w)) + r"\s+(.+)$", norm)
        if m:
            return _strip_trailing(m.group(1).strip(), loc)
    return ""


def _original_case(fragment: str, said: str) -> str:
    """Give back the words as they were said ("Pavarotti", not "pavarotti")."""
    words = fragment.split()
    if not words:
        return fragment
    m = re.search(r"[\W_]+".join(map(re.escape, words)), said, re.IGNORECASE)
    return m.group(0) if m else fragment


def parse(said: str, cfg: dict, loc: Locale) -> dict | None:
    norm = _strip_trailing(normalize(said), loc)
    if not norm:
        return None
    found = []

    # 1. Something to do with a person: email / message / call.
    contact, _ = find_contact(norm, cfg.get("contacts", []))
    if contact:
        for intent, keywords in loc.data["contact_intents"].items():
            pos = _first_keyword(norm, keywords)
            if pos >= 0:
                found.append((pos, {"intent": intent, "contact": contact["name"]}))

    # 2. Something to look for: search / YouTube / map.
    for entry in loc.data["query_intents"]:
        m = _compile(entry["pattern"]).search(norm)
        if not m:
            continue
        q = _original_case(_clean_query(m.groupdict().get("q") or "", loc), said)
        if "q" in entry:
            q = entry["q"].format(q=q).strip()
        if q:
            found.append((m.start(), {"intent": entry["intent"], "q": q}))
            break  # entries are in priority order

    if not found:
        return None
    pos, intent = min(found, key=lambda f: f[0])  # whatever they said first
    if intent["intent"] in ("email", "message"):
        # "…saying I'll be late" / "…that I'll be late": the words to send.
        text = _after(norm, loc.data.get("message_words", []), loc)
        joiners = {normalize(w) for w in loc.data.get("message_words", []) if " " not in w}
        words = text.split()
        while len(words) > 1 and words[0] in joiners:  # "saying that …" -> "…"
            words.pop(0)
        text = _original_case(" ".join(words), said)
        intent["text"] = text
    if intent["intent"] == "email":
        subject = _after(norm, loc.data.get("subject_words", []), loc)
        intent["subject"] = _original_case(subject, said)
        if intent["text"] and intent["subject"].endswith(intent["text"]):
            # "about lunch saying I'll be late": the subject stops where the message starts.
            intent["subject"] = _strip_words(intent["subject"][: -len(intent["text"])], loc)
    return intent


def _strip_words(text: str, loc: Locale) -> str:
    """Drop a dangling "saying"/"that" left at the end of a subject."""
    words = text.split()
    endings = {normalize(w) for w in loc.data.get("message_words", []) if " " not in w}
    while words and normalize(words[-1]) in endings:
        words.pop()
    return " ".join(words).strip()


# ---- Where each request goes -------------------------------------------------

def email_link(service: str, to: str, subject: str = "", body: str = "") -> str:
    if service == "outlook":
        params = {"to": to, "subject": subject}
        if body:
            params["body"] = body
        return "https://outlook.live.com/mail/0/deeplink/compose?" + urlencode(params)
    if service == "mailto":
        extra = {k: v for k, v in (("subject", subject), ("body", body)) if v}
        query = "&".join(f"{k}={quote(v)}" for k, v in extra.items())
        return f"mailto:{quote(to, safe='@')}" + (f"?{query}" if query else "")
    params = {"view": "cm", "fs": "1", "to": to}
    if subject:
        params["su"] = subject
    if body:
        params["body"] = body
    return "https://mail.google.com/mail/?" + urlencode(params)


def whatsapp_link(messaging: str, phone: str, text: str = "") -> str:
    params = {"phone": phone}
    if text:
        params["text"] = text
    if messaging == "whatsapp_web":
        return "https://web.whatsapp.com/send?" + urlencode(params)
    return "whatsapp://send?" + urlencode(params)


def search_link(q: str) -> str:
    return "https://www.google.com/search?" + urlencode({"q": q})


def youtube_link(q: str) -> str:
    return "https://www.youtube.com/results?" + urlencode({"search_query": q})


def map_link(place: str) -> str:
    return "https://www.google.com/maps/dir/?" + urlencode({"api": "1", "destination": place})
