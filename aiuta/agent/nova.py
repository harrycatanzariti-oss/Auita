"""The Basic plan: Amazon Nova (Micro or Lite) through Amazon Bedrock.

Nova is very cheap (roughly $0.035-$0.06 per million words in), which is
what makes a few-dollars-a-month plan possible. Because Aiuta reads the
screen as text, even text-only Nova Micro can do the steps.

It talks to Bedrock's Converse API with a Bedrock API key, using plain
HTTPS, so Aiuta doesn't need Amazon's (large) SDK.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from urllib.parse import quote

from .providers import Call, Provider, ProviderError, Turn

# Bedrock serves Nova through "inference profiles" named after the area.
_AREA = (("us-gov", "us-gov."), ("us", "us."), ("eu", "eu."), ("ap", "apac."), ("ca", "ca."))


def model_id(model: str, region: str) -> str:
    """'amazon.nova-lite-v1:0' in 'ap-southeast-2' -> 'apac.amazon.nova-lite-v1:0'."""
    if not model.startswith("amazon."):
        return model  # already a profile id or ARN
    for prefix, area in _AREA:
        if region.startswith(prefix):
            return area + model
    return model


class NovaProvider(Provider):
    def __init__(self, api_key: str, region: str = "us-east-1",
                 model: str = "amazon.nova-lite-v1:0", timeout: float = 60):
        self.api_key = api_key or os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "")
        if not self.api_key:
            raise ProviderError("No Amazon Bedrock API key")
        self.region = region or "us-east-1"
        self.model = model_id(model or "amazon.nova-lite-v1:0", self.region)
        self.timeout = timeout
        self.messages: list[dict] = []
        self.system = ""
        self.tools: list[dict] = []

    @property
    def url(self) -> str:
        return (f"https://bedrock-runtime.{self.region}.amazonaws.com/model/"
                f"{quote(self.model, safe='')}/converse")

    def start(self, system: str, tools: list[dict]) -> None:
        self.system = system
        self.tools = [{"toolSpec": {"name": t["name"], "description": t["description"],
                                    "inputSchema": {"json": t["schema"]}}} for t in tools]
        self.messages = []

    def add_user(self, text: str) -> None:
        self.messages.append({"role": "user", "content": [{"text": text}]})

    def add_results(self, results) -> None:
        self.messages.append({"role": "user", "content": [
            {"toolResult": {"toolUseId": cid, "content": [{"text": text or "(empty)"}],
                            "status": "error" if err else "success"}}
            for cid, text, err in results]})

    def body(self) -> dict:
        body = {
            "messages": self.messages,
            "system": [{"text": self.system}],
            "inferenceConfig": {"maxTokens": 1000, "temperature": 0},
        }
        if self.tools:
            body["toolConfig"] = {"tools": self.tools}
        return body

    def _post(self, body: dict) -> dict:
        req = urllib.request.Request(
            self.url, data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json",
                     "Authorization": f"Bearer {self.api_key}"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            raise ProviderError(f"Bedrock said {e.code}: {detail}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            raise ProviderError(f"Couldn't reach Bedrock: {e}") from e

    def next(self) -> Turn:
        data = self._post(self.body())
        message = (data.get("output") or {}).get("message") or {"role": "assistant", "content": []}
        self.messages.append(message)
        turn = Turn()
        texts = []
        for block in message.get("content", []):
            if "text" in block:
                texts.append(block["text"])
            elif "toolUse" in block:
                use = block["toolUse"]
                turn.calls.append(Call(use["toolUseId"], use["name"], use.get("input") or {}))
        turn.text = " ".join(t.strip() for t in texts if t.strip())
        if data.get("stopReason") in ("guardrail_intervened", "content_filtered"):
            turn.refused = True
        return turn
