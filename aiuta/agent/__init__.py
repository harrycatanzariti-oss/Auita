"""The AI agent behind the Basic and Plus plans. See loop.py."""
from __future__ import annotations

from .desktop import Desktop, default_desktop
from .loop import Agent


def build(cfg: dict, brain, desktop: Desktop | None = None, make_provider=None) -> Agent | None:
    """The agent for this plan, or None on the free plan (or if it isn't set up)."""
    plan = cfg.get("plan", "free")
    if plan == "free" and make_provider is None:
        return None
    if make_provider is None:
        if plan == "basic":
            from .nova import NovaProvider

            b = cfg["basic"]
            if not b.get("api_key"):
                return None

            def make_provider():
                return NovaProvider(b["api_key"], b["region"], b["model"])
        else:
            from .claude import ClaudeProvider

            import os

            p = cfg["plus"]
            if not (p.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")):
                return None

            def make_provider():
                return ClaudeProvider(p.get("api_key", ""), p.get("model", ""))
    return Agent(brain, make_provider, desktop or default_desktop(), cfg.get("agent_mode", "do"))
