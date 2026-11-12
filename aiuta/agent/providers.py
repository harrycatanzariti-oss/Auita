"""What every AI connection looks like to the agent.

Each connection keeps its own conversation history in its own format and
gives back a Turn: some words, and/or some tool calls.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Call:
    id: str
    name: str
    args: dict


@dataclass
class Turn:
    text: str = ""
    calls: list[Call] = field(default_factory=list)
    refused: bool = False


class ProviderError(RuntimeError):
    pass


class Provider:
    """start() once, then add_user() / add_results() and next() in a loop."""

    def start(self, system: str, tools: list[dict]) -> None:
        raise NotImplementedError

    def add_user(self, text: str) -> None:
        raise NotImplementedError

    def add_results(self, results: list[tuple[str, str, bool]]) -> None:
        """results: (call id, text, is_error)"""
        raise NotImplementedError

    def next(self) -> Turn:
        raise NotImplementedError


class ScriptedProvider(Provider):
    """For tests: plays back a list of Turns and records what it was sent."""

    def __init__(self, turns: list[Turn]):
        self.turns = list(turns)
        self.system = ""
        self.tools: list[dict] = []
        self.sent: list = []

    def start(self, system: str, tools: list[dict]) -> None:
        self.system, self.tools = system, tools

    def add_user(self, text: str) -> None:
        self.sent.append(("user", text))

    def add_results(self, results) -> None:
        self.sent.append(("results", results))

    def next(self) -> Turn:
        if not self.turns:
            return Turn(text="Done.")
        return self.turns.pop(0)
