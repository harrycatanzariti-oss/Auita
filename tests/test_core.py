import json
import urllib.error
import urllib.request

import pytest

from aiuta import actions, config, matcher
from aiuta.brain import Brain
from aiuta.setup_server import MASK, SetupServer

SHORTCUTS = [
    {"name": "Email", "action": "open_website", "target": "mail.google.com",
     "phrases": ["emails", "my mail", "check my messages"]},
    {"name": "Call Marco", "action": "call", "target": "whatsapp://",
     "phrases": ["ring Marco", "video call Marco"]},
    {"name": "Photos", "action": "open_folder", "target": "/home/nonno/Pictures",
     "phrases": ["pictures", "the grandkids photos"]},
    {"name": "Pills", "action": "say", "target": "Take the blue pill with breakfast."},
]


@pytest.fixture
def cfg():
    return config.validate({"shortcuts": SHORTCUTS})


def brain(cfg):
    return Brain(cfg, runner=actions.Runner(dry_run=True))


def test_validate_fills_defaults_and_fixes_urls(cfg):
    email = cfg["shortcuts"][0]
    assert email["target"] == "https://mail.google.com"
    assert email["phrases"][0] == "Email"
    assert cfg["confidence_run"] > cfg["confidence_ask"]


@pytest.mark.parametrize("bad, msg", [
    ({"name": "", "action": "say", "target": "x"}, "needs a name"),
    ({"name": "X", "action": "format_disk", "target": "x"}, "unknown action"),
    ({"name": "X", "action": "say", "target": ""}, "needs something"),
])
def test_validate_rejects_bad_shortcuts(bad, msg):
    with pytest.raises(config.ConfigError, match=msg):
        config.validate({"shortcuts": [bad]})


def test_duplicate_names_rejected():
    s = {"name": "Email", "action": "say", "target": "x"}
    with pytest.raises(config.ConfigError, match="both called"):
        config.validate({"shortcuts": [s, dict(s, name="email")]})


@pytest.mark.parametrize("said, expected", [
    ("open my email", "Email"),
    ("can you show me my emails please", "Email"),
    ("e-mail", "Email"),
    ("check my messages", "Email"),
    ("ring marco", "Call Marco"),
    ("I want to video call Marco", "Call Marco"),
    ("show me the pictures", "Photos"),
    ("photo", "Photos"),
    ("pills", "Pills"),
])
def test_runs_the_right_shortcut(cfg, said, expected):
    b = brain(cfg)
    r = b.hear(said)
    assert r.ran == expected, (said, r)


def test_say_action_reads_text(cfg):
    assert brain(cfg).hear("pills").reply == "Take the blue pill with breakfast."


def test_builtins(cfg):
    b = brain(cfg)
    assert b.hear("what time is it").reply.startswith("It's ")
    listed = b.hear("what can I say").reply
    assert "Email" in listed and "Call Marco" in listed and ", or Pills" in listed
    assert b.runner.log == []


def test_unclear_asks_then_yes_runs(cfg):
    b = brain(cfg)
    r = b.hear("foto")
    assert r.ran == "" and r.question == "Photos"
    assert r.reply == "Did you mean Photos?"
    assert b.hear("yes").ran == "Photos"


def test_did_you_mean_no(cfg):
    b = brain(cfg)
    b.pending = cfg["shortcuts"][0]
    assert b.hear("no").ran == ""
    assert b.pending is None


def test_nonsense_is_not_run(cfg):
    b = brain(cfg)
    r = b.hear("the weather in tuscany tomorrow")
    assert r.ran == "" and not r.question
    assert b.runner.log == []


def test_empty(cfg):
    assert "didn't catch" in brain(cfg).hear("   ").reply


def test_ai_used_only_when_unsure(cfg):
    class FakeAI:
        calls = []

        def handle(self, said, b):
            self.calls.append(said)
            return b.run_shortcut("Photos")

    b = brain(cfg)
    b.assistant = FakeAI()
    assert b.hear("open my email").ran == "Email"
    assert FakeAI.calls == []
    assert b.hear("I'd love to look at the little ones from Christmas").ran == "Photos"
    assert len(FakeAI.calls) == 1


def test_ai_failure_falls_back(cfg):
    class Broken:
        def handle(self, said, b):
            raise RuntimeError("no internet")

    b = brain(cfg)
    b.assistant = Broken()
    assert "didn't understand" in b.hear("the weather in tuscany").reply


def test_yes_or_no():
    assert matcher.yes_or_no("yes please") == "yes"
    assert matcher.yes_or_no("sì") == "yes"
    assert matcher.yes_or_no("no not that") == "no"
    assert matcher.yes_or_no("open the photos") is None


# ---- setup page -------------------------------------------------------------

@pytest.fixture
def server(tmp_path):
    changed = []
    s = SetupServer(on_change=changed.append, cfg_path=tmp_path / "config.json",
                    runner=actions.Runner(dry_run=True))
    s.start(open_browser=False)
    s.changed = changed
    yield s
    s.stop()


def call(server, path, body=None, key=True):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-Aiuta-Key"] = server.token
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"http://127.0.0.1:{server.port}{path}", data=data, headers=headers)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_setup_requires_key(server):
    assert call(server, "/", key=False)[0] == 403
    assert call(server, "/api/config", {"shortcuts": []}, key=False)[0] == 403
    status, page = call(server, f"/?key={server.token}", key=False)
    assert status == 200 and b"Aiuta Setup" in page


def test_setup_save_and_load(server):
    body = {"person_name": "Nonno Gino", "shortcuts": SHORTCUTS,
            "ai": {"enabled": True, "api_key": "sk-secret"}}
    status, _ = call(server, "/api/config", body)
    assert status == 200
    assert server.changed[-1]["person_name"] == "Nonno Gino"
    status, raw = call(server, "/api/config")
    got = json.loads(raw)
    assert got["ai"]["api_key"] == MASK  # never sent back to the page
    # Saving the masked value keeps the real key.
    call(server, "/api/config", got)
    assert config.load(server.cfg_path)["ai"]["api_key"] == "sk-secret"


def test_setup_rejects_bad_config(server):
    status, raw = call(server, "/api/config", {"shortcuts": [{"name": "X", "action": "rm"}]})
    assert status == 400 and b"unknown action" in raw


def test_setup_try_it(server):
    status, raw = call(server, "/api/test", SHORTCUTS[0])
    assert status == 200 and json.loads(raw)["reply"] == "Opening Email."
    assert server.runner.log == [("open_website", "https://mail.google.com")]


def test_example_config_is_valid():
    from pathlib import Path
    cfg = config.load(Path(__file__).parent.parent / "examples" / "config.example.json")
    b = brain(cfg)
    assert b.hear("I'm stuck").ran == "Get help"
    assert b.hear("talk to harry").ran == "Video call Harry"
    assert b.hear("put the football on").ran == "Football"
