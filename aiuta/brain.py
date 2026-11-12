"""Turns what was said into what to do, with no screen or microphone involved.

Order of checks for each thing they say:
  1. Answering a "Did you mean …?" question (yes / no)
  2. A request with something in it: "email Mary", "search for …"
  3. A shortcut or built-in phrase: "photos", "what time is it"
  4. The AI helper, if switched on
  5. "Did you mean …?" if it was close, otherwise "I didn't understand"
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from . import actions, i18n, intents, matcher


@dataclass
class Result:
    reply: str
    ran: str = ""                 # what was opened, if anything
    question: str = ""            # the shortcut we're asking "Did you mean …?" about
    heard: str = ""

    def to_dict(self) -> dict:
        return {"reply": self.reply, "ran": self.ran, "question": self.question, "heard": self.heard}


@dataclass
class Brain:
    cfg: dict
    runner: actions.Runner = field(default_factory=actions.Runner)
    assistant: object | None = None   # aiuta.assistant.Assistant when the AI version is on
    pending: dict | None = None       # shortcut waiting for a yes/no

    @property
    def loc(self) -> i18n.Locale:
        return i18n.get(self.cfg["language"])

    def t(self, key: str, **kw) -> str:
        return self.loc.t(key, helper=self.cfg["helper_name"], **kw)

    # ---- doing things ----------------------------------------------------

    def _open(self, action: str, target: str, name: str, reply: str) -> Result:
        try:
            self.runner.open(action, target)
        except Exception:
            return Result(self.t("couldnt_open", name=name))
        return Result(reply, ran=name)

    def _find(self, items: list[dict], name: str) -> dict | None:
        for item in items:
            if item["name"].lower() == (name or "").lower():
                return item
        return None

    def run_shortcut(self, name: str) -> Result:
        sc = self._find(self.cfg["shortcuts"], name)
        if not sc:
            return Result(self.t("not_set_up", name=name))
        reply = sc.get("reply") or {
            "say": sc["target"],
            "call": self.t("calling", name=sc["name"]),
            "remote_help": self.t("opening_help"),
        }.get(sc["action"], self.t("opening", name=sc["name"]))
        return self._open(sc["action"], sc["target"], sc["name"], reply)

    def act(self, intent: dict) -> Result:
        """Carry out a request from intents.parse() (or from the AI helper)."""
        kind = intent.get("intent")
        q = (intent.get("q") or "").strip()
        if kind == "search" and q:
            return self._open("open_website", intents.search_link(q), q, self.t("searching", q=q))
        if kind == "youtube" and q:
            return self._open("open_website", intents.youtube_link(q), "YouTube",
                              self.t("youtube", q=q))
        if kind == "directions" and q:
            return self._open("open_website", intents.map_link(q), q, self.t("directions", q=q))

        person = self._find(self.cfg["contacts"], intent.get("contact", ""))
        if not person:
            return Result(self.t("not_set_up", name=intent.get("contact", "")))
        who = person["name"]
        if kind == "email":
            if not person["email"]:
                return Result(self.t("no_email", contact=who))
            link = intents.email_link(self.cfg["email_service"], person["email"],
                                      intent.get("subject", ""))
            action = "open_link" if link.startswith("mailto:") else "open_website"
            return self._open(action, link, who, self.t("email_to", contact=who))
        if kind == "call" and person["call_link"]:
            return self._open("call", person["call_link"], who, self.t("call_link", contact=who))
        if kind in ("message", "call"):
            if not person["phone"]:
                return Result(self.t("no_phone", contact=who))
            link = intents.whatsapp_link(self.cfg["messaging"], person["phone"],
                                         intent.get("text", ""))
            action = "open_website" if link.startswith("http") else "open_link"
            reply = self.t("call_to" if kind == "call" else "message_to", contact=who)
            return self._open(action, link, who, reply)
        return Result(self.t("not_understood"))

    def builtin(self, name: str, now: dt.datetime | None = None) -> str:
        now = now or dt.datetime.now()
        if name == "time":
            return self.t("time", time=self.loc.time(now))
        if name == "date":
            return self.t("date", date=self.loc.date(now))
        names = [s["name"] for s in self.cfg["shortcuts"]]
        names += [c["name"] for c in self.cfg["contacts"]]
        if not names:
            return self.t("list_empty")
        return self.t("list", items=self.loc.join_or(names))

    # ---- listening -------------------------------------------------------

    def hear(self, said: str) -> Result:
        r = self._hear((said or "").strip())
        r.heard = said
        return r

    def _hear(self, said: str) -> Result:
        if not said:
            return Result(self.t("didnt_catch"))

        if self.pending:
            answer = matcher.yes_or_no(said, self.loc)
            sc, self.pending = self.pending, None
            if answer == "yes":
                return self.run_shortcut(sc["name"])
            if answer == "no":
                return Result(self.t("okay_what"))
            # Not a yes or no: treat it as a new request.

        intent = intents.parse(said, self.cfg, self.loc)
        if intent:
            return self.act(intent)

        m = matcher.best_match(said, self.cfg["shortcuts"], self.loc)
        if m.score >= self.cfg["confidence_run"]:
            if m.kind == "builtin":
                return Result(self.builtin(m.name))
            return self.run_shortcut(m.name)

        if self.assistant is not None:
            try:
                return self.assistant.handle(said, self)
            except Exception:
                pass  # no internet, bad key...: carry on with the free behaviour

        if m.score >= self.cfg["confidence_ask"] and m.kind == "shortcut":
            self.pending = m.shortcut
            return Result(self.t("did_you_mean", name=m.name), question=m.name)

        return Result(self.t("not_understood"))
