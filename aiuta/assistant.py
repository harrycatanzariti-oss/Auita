"""The optional AI version: talk naturally, ask questions, get things done.

Only used when "ai.enabled" is on and an Anthropic API key is set. The AI can
answer questions and run the shortcuts the family set up, and nothing else:
it cannot click, type, install, buy or delete anything.

Needs: pip install anthropic
"""
from __future__ import annotations

import os

from .brain import Result

SYSTEM = """You are a patient, warm helper on the computer of {person}, an older person \
who finds computers confusing. They talk to you out loud and hear your reply read aloud.

Rules:
- Reply in one to three short, plain sentences. No lists, no markdown, no jargon, no links.
- To open something, call the run_shortcut tool with one of the shortcuts below. Never \
claim you opened something unless the tool said it ran.
- If they want something that isn't in the list, say kindly that it isn't set up yet and \
that {helper} can add it.
- Never ask for passwords, bank details or codes. If they mention a call, message or \
email asking for money, gift cards, passwords or remote access, tell them gently it may \
be a scam and to check with {helper} first.
- Reply in the language they speak to you in.

Shortcuts the family set up:
{shortcuts}"""


class Assistant:
    def __init__(self, cfg: dict):
        import anthropic  # imported here so the free version never needs it

        key = cfg["ai"].get("api_key") or os.environ.get("ANTHROPIC_API_KEY") or None
        self.client = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
        self.model = cfg["ai"].get("model") or "claude-opus-5-5"
        self.cfg = cfg
        self.history: list = []

    def _tools(self) -> list[dict]:
        names = [s["name"] for s in self.cfg["shortcuts"]] or ["(none)"]
        return [{
            "name": "run_shortcut",
            "description": "Open one of the shortcuts the family set up on this computer.",
            "strict": True,
            "input_schema": {
                "type": "object",
                "properties": {"name": {"type": "string", "enum": names}},
                "required": ["name"],
                "additionalProperties": False,
            },
        }]

    def _system(self) -> str:
        lines = [f"- {s['name']} ({s['action'].replace('_', ' ')})" for s in self.cfg["shortcuts"]]
        return SYSTEM.format(
            person=self.cfg["person_name"],
            helper=self.cfg["helper_name"],
            shortcuts="\n".join(lines) or "- none yet",
        )

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
                system=self._system(),
                tools=self._tools(),
                messages=self.history,
                output_config={"effort": "low"},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
            if response.stop_reason == "refusal":
                self.history.pop()
                return Result("Sorry, I can't help with that one. Ask the family.", heard=said)
            self.history.append({"role": "assistant", "content": response.content})
            calls = [b for b in response.content if b.type == "tool_use"]
            if response.stop_reason != "tool_use" or not calls:
                text = " ".join(b.text for b in response.content if b.type == "text").strip()
                return Result(text or "Okay.", ran=ran, heard=said)
            results = []
            for call in calls:
                name = (call.input or {}).get("name", "")
                r = brain.run_shortcut(name)
                ran = r.ran or ran
                results.append({"type": "tool_result", "tool_use_id": call.id, "content": r.reply})
            self.history.append({"role": "user", "content": results})
        return Result("Okay.", ran=ran, heard=said)
