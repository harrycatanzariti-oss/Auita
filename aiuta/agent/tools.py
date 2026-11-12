"""The things the agent can do, and the safety checks around each one.

The same tools are used whichever AI is behind it (Amazon Nova or Claude).
Tool definitions are plain JSON Schema; each AI connection converts them to
its own format.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import safety
from .desktop import Desktop, Screen

KEYS = ["enter", "ctrl+enter", "tab", "escape", "page down", "page up", "up", "down"]


@dataclass
class Outcome:
    text: str                 # what the AI is told
    progress: str = ""        # what the person sees ("Pressing Send…")
    ran: str = ""             # something was opened
    confirm: str = ""         # needs a "yes" from the person first: the question to ask
    stop: str = ""            # stop the whole task and tell the person this
    error: bool = False


def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"name": name, "description": description,
            "schema": {"type": "object", "properties": properties, "required": required,
                       "additionalProperties": False}}


def definitions(cfg: dict, screen_available: bool) -> list[dict]:
    text = {"type": "string"}
    tools = [
        _tool("web_search", "Open a Google search in their browser.", {"query": text}, ["query"]),
        _tool("youtube", "Open YouTube search results (a singer, a recipe, a match).",
              {"query": text}, ["query"]),
        _tool("map", "Open the map with directions to a place.", {"place": text}, ["place"]),
    ]
    shortcuts = [s["name"] for s in cfg["shortcuts"]]
    if shortcuts:
        tools.append(_tool("open_shortcut", "Open one of the things the family set up.",
                           {"name": {"type": "string", "enum": shortcuts}}, ["name"]))
    people = [c["name"] for c in cfg["contacts"]]
    if people:
        person = {"type": "string", "enum": people}
        tools += [
            _tool("write_email",
                  "Open a new email to this person with the subject and message already written in, "
                  "in the person's own voice. To send it, read_screen and click the Send button.",
                  {"person": person, "subject": text, "message": text}, ["person", "subject", "message"]),
            _tool("write_message",
                  "Open their WhatsApp chat with this person with the message already written in. "
                  "To send it, read_screen and press the send button (or the enter key).",
                  {"person": person, "message": text}, ["person", "message"]),
            _tool("call", "Open a video call with this person (or their chat, with the call button).",
                  {"person": person}, ["person"]),
        ]
    if screen_available:
        question = {"type": "string", "description":
                    "If this sends, buys, pays, deletes, posts or can't be undone: a short yes/no "
                    "question for the person, in their language, e.g. 'Shall I send the email to "
                    "Mary?'. Otherwise an empty string."}
        tools += [
            _tool("read_screen",
                  "See what is on the screen now: the window title, numbered buttons, links and "
                  "boxes, and the text. Do this before clicking or typing, and again after.", {}, []),
            _tool("click", "Press a button or link from the last read_screen, by its number.",
                  {"number": {"type": "integer"}, "question": question}, ["number", "question"]),
            _tool("type_text", "Type into a box from the last read_screen, by its number.",
                  {"number": {"type": "integer"}, "text": text}, ["number", "text"]),
            _tool("press_key", "Press a key on the keyboard.",
                  {"key": {"type": "string", "enum": KEYS}, "question": question},
                  ["key", "question"]),
            _tool("wait", "Wait two seconds for something to finish loading.", {}, []),
        ]
    return tools


class ToolRunner:
    def __init__(self, brain, desktop: Desktop, mode: str = "do"):
        self.brain = brain
        self.desktop = desktop
        self.mode = mode
        self.screen: Screen | None = None

    def t(self, key: str, **kw) -> str:
        return self.brain.t(key, **kw)

    def run(self, name: str, args: dict, approved: bool = False) -> Outcome:
        try:
            return self._run(name, args or {}, approved)
        except Exception as e:  # a tool failing is information for the AI, not a crash
            return Outcome(f"That didn't work: {e}", error=True)

    def _opened(self, result) -> Outcome:
        if result.ran:
            return Outcome(f"Done. Aiuta told the person: {result.reply}", progress=result.reply,
                           ran=result.ran)
        return Outcome(f"Not done: {result.reply}", error=True)

    def _run(self, name: str, a: dict, approved: bool) -> Outcome:
        b = self.brain
        if name == "web_search":
            return self._opened(b.act({"intent": "search", "q": a.get("query", "")}))
        if name == "youtube":
            return self._opened(b.act({"intent": "youtube", "q": a.get("query", "")}))
        if name == "map":
            return self._opened(b.act({"intent": "directions", "q": a.get("place", "")}))
        if name == "open_shortcut":
            return self._opened(b.run_shortcut(a.get("name", "")))
        if name == "write_email":
            out = self._opened(b.act({"intent": "email", "contact": a.get("person", ""),
                                      "subject": a.get("subject", ""), "text": a.get("message", "")}))
            if out.ran:
                out.progress = self.t("step_writing_email", contact=out.ran)
            return out
        if name == "write_message":
            out = self._opened(b.act({"intent": "message", "contact": a.get("person", ""),
                                      "text": a.get("message", "")}))
            if out.ran:
                out.progress = self.t("step_writing_message", contact=out.ran)
            return out
        if name == "call":
            return self._opened(b.act({"intent": "call", "contact": a.get("person", "")}))
        if name == "wait":
            self.desktop.wait(2.0)
            return Outcome("Waited 2 seconds.", progress=self.t("step_waiting"))
        if name == "read_screen":
            screen = self.desktop.read()
            if safety.is_blocked(screen.title):
                return Outcome("Blocked page.", stop=self.t("agent_blocked"))
            self.screen = screen
            return Outcome(screen.describe(), progress=self.t("step_reading"))
        if name in ("click", "type_text", "press_key"):
            return self._act_on_screen(name, a, approved)
        return Outcome(f"There is no tool called {name}.", error=True)

    def _act_on_screen(self, name: str, a: dict, approved: bool) -> Outcome:
        if self.mode == "show":
            return Outcome("You are in 'show me' mode: don't press or type anything. Tell the "
                           "person exactly which button to press and where it is on the screen.",
                           error=True)
        if self.screen is None:
            return Outcome("Use read_screen first.", error=True)
        # Check the window right now (it may have changed), not just when it was read.
        if safety.is_blocked(self.desktop.current_title()) or safety.is_blocked(self.screen.title):
            return Outcome("Blocked page.", stop=self.t("agent_blocked"))
        asked = (a.get("question") or "").strip()

        if name == "press_key":
            key = a.get("key", "")
            if key not in KEYS:
                return Outcome(f"Unknown key {key}.", error=True)
            if not approved and (asked or safety.is_risky_key(key, self.screen.title)):
                return Outcome("", confirm=asked or self.t("confirm_press", name=key))
            self.desktop.press(key, self.screen)
            self.screen = None  # the screen has changed: read it again
            return Outcome(f"Pressed {key}.", progress=self.t("step_key", name=key))

        element = self.screen.find(int(a.get("number", 0) or 0))
        if element is None:
            return Outcome("There is no element with that number. Use read_screen again.", error=True)

        if name == "type_text":
            if element.password:
                return Outcome("Never type into password boxes. Stop and tell the person to ask "
                               "their family for help.", stop=self.t("agent_blocked"))
            self.desktop.type(element, str(a.get("text", "")))
            return Outcome(f'Typed into "{element.name}".', progress=self.t("step_typing"))

        # click
        if not approved and (asked or safety.is_risky_button(element.name)):
            return Outcome("", confirm=asked or self.t("confirm_press", name=element.name))
        self.desktop.click(element)
        self.screen = None
        return Outcome(f'Pressed "{element.name}".', progress=self.t("step_clicking", name=element.name))
