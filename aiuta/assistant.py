"""The optional AI version: talk naturally, ask questions, get things done.

Only used when "ai.enabled" is on and an Anthropic API key is set, and only
when the free version didn't understand, so everyday requests stay free.

The AI can answer questions and take them to the same places the free version
can (shortcuts, a search, YouTube, the map, a new email or chat with someone
the family added). It cannot click, type, send, install, buy or delete.
"""
from __future__ import annotations

import os

from .brain import Result

SYSTEM = """You are Aiuta, a patient, warm helper on the computer of {person}, an older \
person who finds computers confusing. They talk to you out loud and hear your reply read aloud.

How to help:
- Reply in one to three short, plain sentences. No lists, no markdown, no jargon, no links.
- When they want to go somewhere or do something, use a tool to take them to the right \
screen, then tell them the one next thing to press. You can't press it for them.
- Never claim you opened something unless the tool result says so.
- If they want something no tool can do, say kindly that it isn't set up yet and that \
{helper} can add it.
- Never ask for passwords, bank details or codes. If they mention a call, message or email \
asking for money, gift cards, passwords or remote access, tell them gently it may be a scam \
and to check with {helper} first.
- Reply in the language they speak to you in. Their usual language is {language}.

Shortcuts the family set up:
{shortcuts}

People the family added:
{people}"""


class Assistant:
    def __init__(self, cfg: dict):
        import anthropic  # imported here so the free version never needs it

        key = cfg["ai"].get("api_key") or os.environ.get("ANTHROPIC_API_KEY") or None
        self.client = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
        self.model = cfg["ai"].get("model") or "claude-opus-5-5"
        self.cfg = cfg
        self.history: list = []

    # ---- tools -------------------------------------------------------------

    def _tools(self) -> list[dict]:
        def tool(name, description, properties, required):
            return {"name": name, "description": description, "strict": True,
                    "input_schema": {"type": "object", "properties": properties,
                                     "required": required, "additionalProperties": False}}

        text = {"type": "string"}
        tools = [
            tool("web_search", "Open a Google search in their browser.", {"query": text}, ["query"]),
            tool("youtube", "Open YouTube search results, e.g. a singer, a recipe video, a match.",
                 {"query": text}, ["query"]),
            tool("map", "Open the map with directions to a place.", {"place": text}, ["place"]),
        ]
        shortcuts = [s["name"] for s in self.cfg["shortcuts"]]
        if shortcuts:
            tools.append(tool("open_shortcut", "Open one of the shortcuts the family set up.",
                              {"name": {"type": "string", "enum": shortcuts}}, ["name"]))
        people = [c["name"] for c in self.cfg["contacts"]]
        if people:
            person = {"type": "string", "enum": people}
            tools += [
                tool("new_email", "Open a new email to this person, ready for them to type and send.",
                     {"person": person, "subject": text}, ["person", "subject"]),
                tool("message", "Open their WhatsApp chat with this person.",
                     {"person": person}, ["person"]),
                tool("call", "Open a video call with this person (or their chat, with the call button).",
                     {"person": person}, ["person"]),
            ]
        return tools

    def _run_tool(self, name: str, args: dict, brain) -> Result:
        if name == "open_shortcut":
            return brain.run_shortcut(args.get("name", ""))
        intent = {
            "web_search": {"intent": "search", "q": args.get("query", "")},
            "youtube": {"intent": "youtube", "q": args.get("query", "")},
            "map": {"intent": "directions", "q": args.get("place", "")},
            "new_email": {"intent": "email", "contact": args.get("person", ""),
                          "subject": args.get("subject", "")},
            "message": {"intent": "message", "contact": args.get("person", "")},
            "call": {"intent": "call", "contact": args.get("person", "")},
        }.get(name)
        return brain.act(intent) if intent else Result("Unknown tool.")

    def _system(self, brain) -> str:
        shortcuts = [f"- {s['name']}" for s in self.cfg["shortcuts"]]
        people = [f"- {c['name']}" + (f" (also called {', '.join(c['nicknames'])})" if c["nicknames"] else "")
                  for c in self.cfg["contacts"]]
        return SYSTEM.format(
            person=self.cfg["person_name"],
            helper=self.cfg["helper_name"],
            language=brain.loc.data.get("name", "English"),
            shortcuts="\n".join(shortcuts) or "- none yet",
            people="\n".join(people) or "- none yet",
        )

    # ---- conversation ----------------------------------------------------

    def handle(self, said: str, brain) -> Result:
        self.history.append({"role": "user", "content": said})
        self.history = self.history[-20:]  # keep it short and cheap
        # The conversation must start with something they said, not a tool result.
        while self.history and not (
            self.history[0]["role"] == "user" and isinstance(self.history[0]["content"], str)
        ):
            self.history.pop(0)
        ran = ""
        for _ in range(4):
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=1024,
                system=self._system(brain),
                tools=self._tools(),
                messages=self.history,
                output_config={"effort": "low"},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
            if response.stop_reason == "refusal":
                self.history.pop()
                return Result(brain.t("ai_refused"))
            self.history.append({"role": "assistant", "content": response.content})
            calls = [b for b in response.content if b.type == "tool_use"]
            if response.stop_reason != "tool_use" or not calls:
                text = " ".join(b.text for b in response.content if b.type == "text").strip()
                return Result(text or brain.t("okay_what"), ran=ran)
            results = []
            for call in calls:
                r = self._run_tool(call.name, call.input or {}, brain)
                ran = r.ran or ran
                results.append({"type": "tool_result", "tool_use_id": call.id,
                                "content": r.reply if r.ran else f"Not opened: {r.reply}"})
            self.history.append({"role": "user", "content": results})
        return Result(brain.t("okay_what"), ran=ran)
