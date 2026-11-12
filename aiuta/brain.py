"""Turns what was said into what to do, with no screen or microphone involved.

Keeping this separate from the window and the microphone means it can be
tested, and reused by other front ends (a phone app, a smart speaker).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import actions, matcher


@dataclass
class Result:
    reply: str
    ran: str = ""                 # name of the shortcut that ran, if any
    question: str = ""            # name of the shortcut we are asking about
    heard: str = ""


@dataclass
class Brain:
    cfg: dict
    runner: actions.Runner = field(default_factory=actions.Runner)
    assistant: object | None = None   # aiuta.assistant.Assistant when the AI version is on
    pending: dict | None = None       # shortcut waiting for a yes/no

    def _find(self, name: str) -> dict | None:
        for sc in self.cfg["shortcuts"]:
            if sc["name"].lower() == name.lower():
                return sc
        return None

    def run_shortcut(self, name: str) -> Result:
        sc = self._find(name)
        if not sc:
            return Result(f"I don't have {name} set up.")
        return Result(self.runner.run(sc), ran=sc["name"])

    def hear(self, said: str) -> Result:
        said = (said or "").strip()
        if not said:
            return Result("I didn't catch that. Press the button and try again.")

        if self.pending:
            answer = matcher.yes_or_no(said)
            sc, self.pending = self.pending, None
            if answer == "yes":
                r = Result(self.runner.run(sc), ran=sc["name"])
                r.heard = said
                return r
            if answer == "no":
                return Result("Okay. What would you like?", heard=said)
            # Not a yes or no: treat it as a new request.

        m = matcher.best_match(said, self.cfg["shortcuts"])
        if m.score >= self.cfg["confidence_run"]:
            if m.kind == "builtin":
                return Result(actions.builtin_reply(m.name, self.cfg), heard=said)
            return Result(self.runner.run(m.shortcut), ran=m.name, heard=said)

        if self.assistant is not None:
            try:
                return self.assistant.handle(said, self)
            except Exception:
                pass  # fall back to the free behaviour below

        if m.score >= self.cfg["confidence_ask"] and m.kind == "shortcut":
            self.pending = m.shortcut
            return Result(f"Did you mean {m.name}?", question=m.name, heard=said)

        return Result(
            "Sorry, I didn't understand. You can say \"what can I say\" to hear the list.",
            heard=said,
        )
