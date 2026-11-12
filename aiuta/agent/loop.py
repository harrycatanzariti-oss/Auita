"""The agent: does a task for them, step by step, on the Basic and Plus plans.

  "Email Mary that I'll be late on Sunday"
    -> write_email(Mary, "Sunday", "Hi Mary, I'll be a bit late on Sunday. Love, Nonno")
    -> read_screen  -> click [Send]
    -> Aiuta asks "Shall I send the email to Mary?"  (the agent waits)
    -> "Yes" -> presses Send -> "Done, your email to Mary has gone."

It runs in the background so the window stays responsive: the window asks
for status() every moment to show progress, Yes/No questions and a Stop
button.
"""
from __future__ import annotations

import threading
import time

from .desktop import Desktop
from .providers import Provider, ProviderError
from .tools import ToolRunner, definitions

MAX_STEPS = 16
ANSWER_TIMEOUT = 180  # seconds to wait for a yes/no before giving up

SYSTEM = """You are Aiuta, a patient and warm helper on the computer of {person}, an older \
person who finds computers hard. They talk to you out loud and hear your replies read aloud.

Do what they ask using the tools, step by step:
- Prefer the simple tools (write_email, write_message, call, web_search, youtube, map, \
open_shortcut). They open the right screen with everything filled in.
- When writing an email or message for them, write it as them, short and warm, in their \
language, signed "{person}" if it's an email. Keep their meaning; don't invent facts.
- To finish a task on screen: read_screen, then click or type using the numbers, then \
read_screen again to check what happened. Wait if a page is still loading.
- Aiuta itself asks them before anything is sent, bought, deleted or posted. Always fill \
in "question" for those clicks, e.g. "Shall I send the email to Mary?".
- If they say no, stop.
{mode_rule}
Safety:
- Never type passwords, codes, or bank or card details. Never try to sign in.
- If something asks for money, gift cards, passwords, remote access or personal details, or \
looks like a scam, stop and tell them gently to check with {helper} first.
- If you get stuck after a few tries, stop and suggest asking {helper}.

When you finish, reply in one to three short, plain sentences in {language}: what you did, \
or the one thing they need to do next. No lists, no markdown, no links.

Today is {today}.
People the family added: {people}
Shortcuts the family set up: {shortcuts}"""

SHOW_RULE = """- "Show me" mode is on: never press or type anything on the screen. After \
opening the right screen, read_screen and tell them exactly which button to press and \
where it is (for example "the blue Send button at the bottom left")."""


class Agent:
    def __init__(self, brain, make_provider, desktop: Desktop, mode: str = "do"):
        self.brain = brain
        self.make_provider = make_provider
        self.desktop = desktop
        self.mode = mode
        self._lock = threading.Lock()
        self._answer_ready = threading.Event()
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None
        self._answer: bool | None = None
        self.memory: list[tuple[str, str]] = []  # the last few requests and replies
        self._reset()

    def _reset(self) -> None:
        self.working = False
        self.steps: list[str] = []
        self.question = ""
        self.reply = ""
        self.ran = ""

    # ---- what the window sees ---------------------------------------------------

    @property
    def waiting(self) -> bool:
        return self.working and bool(self.question)

    def status(self) -> dict:
        with self._lock:
            return {"working": self.working, "steps": list(self.steps[-6:]),
                    "question": self.question, "reply": self.reply, "ran": self.ran}

    # ---- controls -----------------------------------------------------------------

    def start(self, said: str) -> None:
        with self._lock:
            if self.working:
                return
            self._reset()
            self.working = True
            self._cancel.clear()
            self._answer_ready.clear()
        self._thread = threading.Thread(target=self._run, args=(said,), daemon=True)
        self._thread.start()

    def answer(self, yes: bool) -> None:
        self._answer = yes
        self._answer_ready.set()

    def stop(self) -> None:
        self._cancel.set()
        self._answer = False
        self._answer_ready.set()

    def wait_until_done(self, timeout: float = 10) -> None:
        """For tests and the command line."""
        if self._thread:
            self._thread.join(timeout)

    # ---- the work -------------------------------------------------------------------

    def _system(self) -> str:
        cfg = self.brain.cfg
        people = ", ".join(c["name"] + (f" ({', '.join(c['nicknames'])})" if c["nicknames"] else "")
                           for c in cfg["contacts"]) or "none yet"
        return SYSTEM.format(
            person=cfg["person_name"], helper=cfg["helper_name"],
            language=self.brain.loc.data.get("name", "English"),
            mode_rule=SHOW_RULE if self.mode == "show" else "",
            today=time.strftime("%A %d %B %Y"),
            people=people,
            shortcuts=", ".join(s["name"] for s in cfg["shortcuts"]) or "none yet",
        )

    def _finish(self, reply: str) -> None:
        with self._lock:
            self.reply = reply
            self.question = ""
            self.working = False

    def _step(self, text: str) -> None:
        if text:
            with self._lock:
                self.steps.append(text)

    def _run(self, said: str) -> None:
        t = self.brain.t
        self.desktop.compact(True)
        try:
            provider: Provider = self.make_provider()
            provider.start(self._system(), definitions(self.brain.cfg, self.desktop.available))
            context = "".join(f"(Earlier they asked: {q!r}; you replied: {r!r})\n" for q, r in self.memory)
            provider.add_user(context + said)
            reply = self._loop(provider)
        except ProviderError:
            reply = t("agent_error")
        except Exception:
            reply = t("agent_error")
        finally:
            self.desktop.compact(False)
        self.memory = (self.memory + [(said, reply)])[-2:]
        self._finish(reply)

    def _ask(self, question: str) -> bool:
        with self._lock:
            self.question = question
        self._answer_ready.clear()
        self._answer = None
        got = self._answer_ready.wait(ANSWER_TIMEOUT)
        with self._lock:
            self.question = ""
        return bool(got and self._answer and not self._cancel.is_set())

    def _loop(self, provider: Provider) -> str:
        t = self.brain.t
        runner = ToolRunner(self.brain, self.desktop, self.mode)
        for _ in range(MAX_STEPS):
            if self._cancel.is_set():
                return t("agent_stopped")
            turn = provider.next()
            if turn.refused:
                return t("ai_refused")
            if not turn.calls:
                return turn.text or t("okay_what")
            results = []
            for call in turn.calls:
                if self._cancel.is_set():
                    return t("agent_stopped")
                out = runner.run(call.name, call.args)
                if out.confirm:
                    if not self._ask(out.confirm):
                        return t("agent_stopped") if self._cancel.is_set() else t("agent_declined")
                    out = runner.run(call.name, call.args, approved=True)
                if out.stop:
                    return out.stop
                self._step(out.progress)
                if out.ran:
                    with self._lock:
                        self.ran = out.ran
                results.append((call.id, out.text, out.error))
            provider.add_results(results)
        return t("agent_too_long")
