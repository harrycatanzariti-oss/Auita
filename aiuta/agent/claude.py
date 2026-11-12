"""The Plus plan: Claude, for harder or unusual tasks.

Uses the official Anthropic SDK (bundled in the Windows installer).
"""
from __future__ import annotations

import os

from .providers import Call, Provider, ProviderError, Turn

DEFAULT_MODEL = "claude-opus-5-5"


class ClaudeProvider(Provider):
    def __init__(self, api_key: str = "", model: str = DEFAULT_MODEL, client=None):
        if client is None:
            try:
                import anthropic
            except ImportError as e:
                raise ProviderError("The anthropic package isn't installed") from e
            key = api_key or os.environ.get("ANTHROPIC_API_KEY") or None
            client = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
        self.client = client
        self.model = model or DEFAULT_MODEL
        self.messages: list[dict] = []
        self.system = ""
        self.tools: list[dict] = []

    def start(self, system: str, tools: list[dict]) -> None:
        self.system = system
        self.tools = [{"name": t["name"], "description": t["description"],
                       "input_schema": t["schema"], "strict": True} for t in tools]
        self.messages = []

    def add_user(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})

    def add_results(self, results) -> None:
        self.messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": cid, "content": text or "(empty)",
             "is_error": bool(err)} for cid, text, err in results]})

    def next(self) -> Turn:
        import anthropic

        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=2048,
                system=self.system,
                tools=self.tools,
                messages=self.messages,
                output_config={"effort": "low"},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.APIConnectionError as e:
            raise ProviderError(f"Couldn't reach Claude: {e}") from e
        except anthropic.APIStatusError as e:
            raise ProviderError(f"Claude said {e.status_code}") from e
        if response.stop_reason == "refusal":
            return Turn(refused=True)
        self.messages.append({"role": "assistant", "content": response.content})
        turn = Turn()
        turn.text = " ".join(b.text.strip() for b in response.content
                             if b.type == "text" and b.text.strip())
        turn.calls = [Call(b.id, b.name, b.input or {}) for b in response.content if b.type == "tool_use"]
        return turn
