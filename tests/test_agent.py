"""The AI agent (Basic and Plus plans), with a pretend AI and a pretend screen."""
import json
import time
import urllib.request

import pytest

from aiuta import actions, config
from aiuta.agent import build, nova, safety
from aiuta.agent.claude import ClaudeProvider
from aiuta.agent.desktop import FakeDesktop, Screen, Element
from aiuta.agent.providers import Call, ScriptedProvider, Turn
from aiuta.brain import Brain
from aiuta.server import AiutaServer

from test_core import CONTACTS, SHORTCUTS, call

GMAIL = ("Mary - Compose - Gmail - Microsoft Edge",
         [("button", "Send"), ("edit", "Subject"), ("button", "Discard draft")])


def setup(turns, screen=GMAIL, mode="do", lang="en"):
    cfg = config.validate({"language": lang, "plan": "basic", "agent_mode": mode,
                           "contacts": CONTACTS, "shortcuts": SHORTCUTS})
    brain = Brain(cfg, runner=actions.Runner(dry_run=True))
    desktop = FakeDesktop(*screen)
    provider = ScriptedProvider(turns)
    brain.agent = build(cfg, brain, desktop, lambda: provider)
    return brain, desktop, provider


def run(brain, said):
    r = brain.hear(said)
    assert r.working
    wait_for(lambda: not brain.agent.working or brain.agent.waiting)
    return brain.agent.status()


def wait_for(cond, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return
        time.sleep(0.01)
    raise AssertionError("timed out")


SEND_EMAIL = [
    Turn(calls=[Call("1", "write_email", {"person": "Mary", "subject": "Sunday",
                                          "message": "Hi Mary, I'll be a little late on Sunday. Love, Nonno"})]),
    Turn(calls=[Call("2", "read_screen", {})]),
    Turn(calls=[Call("3", "click", {"number": 1, "question": "Shall I send the email to Mary?"})]),
    Turn(text="Your email to Mary has been sent."),
]


def test_sends_only_after_yes():
    brain, desktop, provider = setup(SEND_EMAIL)
    st = run(brain, "email Mary that I'll be late on Sunday")
    assert st["question"] == "Shall I send the email to Mary?"
    assert ("click", "Send") not in desktop.log          # nothing sent yet
    assert "body=Hi+Mary" in brain.runner.log[-1][1]       # the email was written in
    r = brain.hear("yes")
    assert r.working
    brain.agent.wait_until_done()
    assert ("click", "Send") in desktop.log
    assert brain.agent.status()["reply"] == "Your email to Mary has been sent."
    assert "Looking at the screen…" in brain.agent.status()["steps"]


def test_no_means_nothing_is_sent():
    brain, desktop, _ = setup(SEND_EMAIL)
    run(brain, "email Mary that I'll be late")
    brain.hear("no")
    brain.agent.wait_until_done()
    assert ("click", "Send") not in desktop.log
    assert brain.agent.status()["reply"] == "Okay, I won't do that."


def test_risky_buttons_ask_even_if_the_ai_forgets():
    turns = [Turn(calls=[Call("1", "read_screen", {})]),
             Turn(calls=[Call("2", "click", {"number": 3, "question": ""})])]
    brain, desktop, _ = setup(turns)
    st = run(brain, "get rid of that")
    assert st["question"] == 'Shall I press "Discard draft"?'
    brain.agent.stop()
    brain.agent.wait_until_done()
    assert ("click", "Discard draft") not in desktop.log
    assert brain.agent.status()["reply"] == "Okay, I've stopped."


def test_enter_in_a_chat_asks_first():
    turns = [Turn(calls=[Call("1", "read_screen", {})]),
             Turn(calls=[Call("2", "press_key", {"key": "enter", "question": ""})])]
    brain, desktop, _ = setup(turns, screen=("WhatsApp", [("edit", "Type a message")]))
    st = run(brain, "send it")
    assert st["question"] == 'Shall I press "enter"?'
    brain.agent.stop()


def test_safe_clicks_dont_ask():
    turns = [Turn(calls=[Call("1", "read_screen", {})]),
             Turn(calls=[Call("2", "click", {"number": 2, "question": ""})]),
             Turn(text="Done.")]
    brain, desktop, _ = setup(turns)
    run(brain, "click the subject")
    brain.agent.wait_until_done()
    assert ("click", "Subject") in desktop.log


def test_stops_on_bank_and_sign_in_pages():
    for title in ("NetBank - Commonwealth Bank", "Sign in - Google Accounts", "PayPal Checkout",
                  "Accedi - Poste Italiane"):
        turns = [Turn(calls=[Call("1", "read_screen", {})]), Turn(text="should not get here")]
        brain, desktop, provider = setup(turns, screen=(title, [("button", "Continue")]))
        run(brain, "can you sort this out")
        brain.agent.wait_until_done()
        assert "bank, payment or sign-in" in brain.agent.status()["reply"], title
        assert provider.turns, "the AI must not be shown a blocked page"


def test_never_types_into_password_boxes():
    turns = [Turn(calls=[Call("1", "read_screen", {})]),
             Turn(calls=[Call("2", "type_text", {"number": 1, "text": "hunter2"})])]
    brain, desktop, _ = setup(turns, screen=("Some site", [("password", "Password")]))
    run(brain, "type my password")
    brain.agent.wait_until_done()
    assert not any(e[0] == "type" for e in desktop.log)


def test_show_me_mode_never_presses():
    turns = [Turn(calls=[Call("1", "read_screen", {})]),
             Turn(calls=[Call("2", "click", {"number": 2, "question": ""})]),
             Turn(text="Press the blue Send button at the bottom left.")]
    brain, desktop, provider = setup(turns, mode="show")
    run(brain, "how do I send this")
    brain.agent.wait_until_done()
    assert not any(e[0] == "click" for e in desktop.log)
    assert "show me" in provider.system.lower()
    assert brain.agent.status()["reply"].startswith("Press the blue Send")


def test_simple_requests_stay_free():
    brain, _, provider = setup([Turn(text="should not be used")])
    assert brain.hear("open my email").ran == "Email"
    assert brain.hear("search for pasta").ran
    assert brain.hear("what time is it").reply.startswith("It's")
    assert provider.sent == []


def test_too_many_steps_gives_up_politely():
    turns = [Turn(calls=[Call(str(i), "wait", {})]) for i in range(40)]
    brain, _, _ = setup(turns)
    run(brain, "do something endless")
    brain.agent.wait_until_done()
    assert "taking too long" in brain.agent.status()["reply"]


def test_ai_error_is_explained():
    class Broken(ScriptedProvider):
        def next(self):
            from aiuta.agent.providers import ProviderError
            raise ProviderError("no internet")

    cfg = config.validate({"plan": "basic", "contacts": CONTACTS})
    brain = Brain(cfg, runner=actions.Runner(dry_run=True))
    brain.agent = build(cfg, brain, FakeDesktop("x", []), lambda: Broken([]))
    brain.hear("do something")
    brain.agent.wait_until_done()
    assert "isn't working right now" in brain.agent.status()["reply"]


def test_busy_agent_doesnt_start_twice():
    brain, _, _ = setup(SEND_EMAIL)
    run(brain, "email Mary that I'll be late")
    r = brain.hear("open the photos")
    assert r.question == "Shall I send the email to Mary?"  # still waiting for the answer
    brain.agent.stop()


def test_italian_question_and_replies():
    turns = [Turn(calls=[Call("1", "read_screen", {})]),
             Turn(calls=[Call("2", "click", {"number": 3, "question": ""})])]
    brain, _, _ = setup(turns, lang="it")
    st = run(brain, "butta via la bozza")
    assert st["question"] == 'Premo "Discard draft"?'
    brain.hear("no")
    brain.agent.wait_until_done()
    assert brain.agent.status()["reply"] == "Va bene, non lo faccio."


# ---- safety rules on their own ------------------------------------------------

@pytest.mark.parametrize("name, risky", [
    ("Send", True), ("Invia", True), ("Place order", True), ("Delete", True), ("Elimina", True),
    ("Pay now", True), ("Reply all", True), ("Compose", False), ("Inbox", False),
    ("Posta in arrivo", False), ("Search mail", False), ("Subject", False),
])
def test_risky_buttons(name, risky):
    assert safety.is_risky_button(name) is risky


def test_screen_description_is_short_and_numbered():
    s = Screen("Inbox", [Element(1, "button", "Compose"), Element(2, "edit", "Search", "pasta"),
                         Element(3, "edit", "Password", password=True)], ["Mary Rossi - Sunday lunch"])
    text = s.describe()
    assert '[1] button "Compose"' in text and '[2] edit "Search" = "pasta"' in text
    assert "never type here" in text and "Sunday lunch" in text


# ---- the AI connections (no network) ------------------------------------------

def test_nova_request_and_reply(monkeypatch):
    p = nova.NovaProvider("bedrock-key", "ap-southeast-2", "amazon.nova-lite-v1:0")
    assert p.model == "apac.amazon.nova-lite-v1:0"
    assert p.url == ("https://bedrock-runtime.ap-southeast-2.amazonaws.com/model/"
                     "apac.amazon.nova-lite-v1%3A0/converse")
    p.start("be kind", [{"name": "web_search", "description": "search",
                         "schema": {"type": "object", "properties": {"query": {"type": "string"}},
                                    "required": ["query"], "additionalProperties": False}}])
    p.add_user("search for pasta")
    sent = []

    def fake_post(body):
        sent.append(json.loads(json.dumps(body)))
        return {"output": {"message": {"role": "assistant", "content": [
                    {"text": "Searching."},
                    {"toolUse": {"toolUseId": "t1", "name": "web_search", "input": {"query": "pasta"}}}]}},
                "stopReason": "tool_use"}

    monkeypatch.setattr(p, "_post", fake_post)
    turn = p.next()
    assert turn.text == "Searching." and turn.calls[0].name == "web_search"
    assert turn.calls[0].args == {"query": "pasta"}
    body = sent[0]
    assert body["system"] == [{"text": "be kind"}]
    assert body["toolConfig"]["tools"][0]["toolSpec"]["inputSchema"]["json"]["required"] == ["query"]
    p.add_results([("t1", "Done.", False)])
    assert p.messages[-1]["content"][0]["toolResult"] == {
        "toolUseId": "t1", "content": [{"text": "Done."}], "status": "success"}


def test_nova_model_ids():
    assert nova.model_id("amazon.nova-micro-v1:0", "us-east-1") == "us.amazon.nova-micro-v1:0"
    assert nova.model_id("amazon.nova-lite-v1:0", "eu-west-1") == "eu.amazon.nova-lite-v1:0"
    assert nova.model_id("us.amazon.nova-lite-v1:0", "ap-southeast-2") == "us.amazon.nova-lite-v1:0"


def test_nova_sends_the_key_as_a_bearer_token(monkeypatch):
    p = nova.NovaProvider("bedrock-key", "us-east-1")
    seen = {}

    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, *a): return b'{"output":{"message":{"role":"assistant","content":[{"text":"hi"}]}},"stopReason":"end_turn"}'

    def fake_urlopen(req, timeout=0):
        seen["auth"] = req.get_header("Authorization")
        seen["url"] = req.full_url
        return Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    p.start("s", [])
    p.add_user("hello")
    assert p.next().text == "hi"
    assert seen["auth"] == "Bearer bedrock-key" and seen["url"].endswith("/converse")


def test_claude_request_and_reply():
    anthropic = pytest.importorskip("anthropic")
    httpx = pytest.importorskip("httpx2") if not _has("httpx") else __import__("httpx")
    sent = []
    reply = {"id": "m1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
             "stop_reason": "tool_use", "stop_sequence": None,
             "content": [{"type": "tool_use", "id": "t1", "name": "web_search", "input": {"query": "pasta"}}],
             "usage": {"input_tokens": 1, "output_tokens": 1}}

    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=reply)

    client = anthropic.Anthropic(api_key="sk-test", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    p = ClaudeProvider(client=client)
    p.start("be kind", [{"name": "web_search", "description": "search",
                         "schema": {"type": "object", "properties": {"query": {"type": "string"}},
                                    "required": ["query"], "additionalProperties": False}}])
    p.add_user("search for pasta")
    turn = p.next()
    assert turn.calls[0].args == {"query": "pasta"}
    assert sent[0]["model"] == "claude-opus-5-5" and sent[0]["tools"][0]["strict"] is True
    assert sent[0]["fallbacks"] == "default"


def _has(module):
    try:
        __import__(module)
        return True
    except ImportError:
        return False


# ---- the server and window ---------------------------------------------------------

def test_status_answer_and_stop_over_the_server(tmp_path):
    path = tmp_path / "config.json"
    config.save({"plan": "basic", "contacts": CONTACTS, "shortcuts": SHORTCUTS}, path)
    desktop = FakeDesktop(*GMAIL)
    s = AiutaServer(port=0, cfg_path=path, runner=actions.Runner(dry_run=True),
                    desktop=desktop, make_provider=lambda: ScriptedProvider(list(SEND_EMAIL)))
    s.start()
    try:
        r = json.loads(call(s, "/api/hear", {"text": "email Mary that I'll be late"})[1])
        assert r["working"] is True
        wait_for(lambda: json.loads(call(s, "/api/status")[1])["question"])
        assert json.loads(call(s, "/api/ui")[1])["plan"] == "basic"
        call(s, "/api/answer", {"yes": True})
        wait_for(lambda: not json.loads(call(s, "/api/status")[1])["working"])
        st = json.loads(call(s, "/api/status")[1])
        assert st["reply"] == "Your email to Mary has been sent." and ("click", "Send") in desktop.log
    finally:
        s.stop()


def test_free_plan_has_no_agent(tmp_path):
    cfg = config.validate({"plan": "free"})
    assert build(cfg, Brain(cfg)) is None
    cfg = config.validate({"plan": "basic"})  # no key yet
    assert build(cfg, Brain(cfg)) is None


def test_old_ai_settings_move_to_plus():
    cfg = config.validate({"ai": {"enabled": True, "api_key": "sk-old", "model": "claude-opus-5-5"}})
    assert cfg["plan"] == "plus" and cfg["plus"]["api_key"] == "sk-old"
