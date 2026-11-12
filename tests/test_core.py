import datetime as dt
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from aiuta import actions, config, i18n, intents, matcher
from aiuta.brain import Brain
from aiuta.server import MASK, AiutaServer

ROOT = Path(__file__).resolve().parent.parent

SHORTCUTS = [
    {"name": "Email", "action": "open_website", "target": "mail.google.com",
     "phrases": ["emails", "my mail", "check my messages"]},
    {"name": "Photos", "action": "open_folder", "target": "/home/nonno/Pictures",
     "phrases": ["pictures", "the grandkids photos"]},
    {"name": "Pills", "action": "say", "target": "Take the blue pill with breakfast."},
    {"name": "Get help", "action": "remote_help", "target": "rustdesk.exe",
     "phrases": ["I'm stuck", "something is wrong"]},
]
CONTACTS = [
    {"name": "Mary", "nicknames": "my daughter, Maria", "email": "mary@example.com",
     "phone": "+61 412 345 678"},
    {"name": "Marco", "phone": "+39 333 123 4567"},
    {"name": "Luca", "email": "luca@example.com", "call_link": "https://meet.example.com/luca"},
]


def make_cfg(lang="en", **extra):
    return config.validate({"language": lang, "shortcuts": SHORTCUTS, "contacts": CONTACTS, **extra})


def brain(lang="en", **extra):
    return Brain(make_cfg(lang, **extra), runner=actions.Runner(dry_run=True))


def opened(b):
    return b.runner.log[-1][1] if b.runner.log else None


# ---- settings ------------------------------------------------------------------

def test_validate_fills_defaults_and_cleans():
    cfg = make_cfg()
    assert cfg["shortcuts"][0]["target"] == "https://mail.google.com"
    assert cfg["shortcuts"][0]["phrases"][0] == "Email"
    mary = cfg["contacts"][0]
    assert mary["phone"] == "61412345678" and mary["nicknames"] == ["my daughter", "Maria"]
    assert cfg["confidence_run"] > cfg["confidence_ask"]
    assert config.validate({"language": "klingon"})["language"] == "en"


@pytest.mark.parametrize("bad, msg", [
    ({"shortcuts": [{"name": "", "action": "say", "target": "x"}]}, "needs a name"),
    ({"shortcuts": [{"name": "X", "action": "format_disk", "target": "x"}]}, "unknown action"),
    ({"shortcuts": [{"name": "X", "action": "say", "target": ""}]}, "needs something"),
    ({"contacts": [{"name": "Mary", "email": "not-an-email"}]}, "email address"),
    ({"contacts": [{"name": "Mary", "phone": "1234"}]}, "country code"),
    ({"contacts": [{"name": "Mary"}, {"name": "mary"}]}, "both called"),
])
def test_validate_rejects_bad_entries(bad, msg):
    with pytest.raises(config.ConfigError, match=msg):
        config.validate(bad)


def test_first_run_has_useful_defaults_in_their_language():
    en = config.first_run_config("en")
    it = config.first_run_config("it")
    assert any(s["name"] == "Email" for s in en["shortcuts"])
    assert it["language"] == "it" and any(s["name"] == "Notizie" for s in it["shortcuts"])


def test_secret_key_is_stable(tmp_path):
    k = config.secret_key(tmp_path / "key.txt")
    assert len(k) >= 20 and config.secret_key(tmp_path / "key.txt") == k


# ---- languages -----------------------------------------------------------------

def test_every_language_file_has_every_key():
    en = json.loads((ROOT / "aiuta/locales/en.json").read_text("utf-8"))
    for lang in i18n.available():
        data = json.loads((ROOT / f"aiuta/locales/{lang}.json").read_text("utf-8"))
        for section in ("text", "ui", "setup"):
            missing = set(en[section]) - set(data[section])
            assert not missing, f"{lang}.json is missing {section}: {sorted(missing)}"
        for key in ("speech", "filler", "builtins", "contact_intents", "query_intents",
                    "days", "months", "date_format"):
            assert key in data, f"{lang}.json is missing {key}"
        for entry in data["query_intents"]:
            intents._compile(entry["pattern"])  # every pattern is a valid regex


def test_dates_and_times():
    now = dt.datetime(2026, 11, 12, 13, 5)
    assert i18n.get("en").time(now) == "1:05 PM"
    assert i18n.get("en").date(now) == "Thursday, 12 November 2026"
    assert i18n.get("it").time(now) == "13:05"
    assert i18n.get("it").date(now) == "giovedì 12 novembre 2026"


# ---- shortcuts -----------------------------------------------------------------

@pytest.mark.parametrize("said, expected", [
    ("open my email", "Email"),
    ("can you show me my emails please", "Email"),
    ("e-mail", "Email"),
    ("check my messages", "Email"),
    ("show me the pictures", "Photos"),
    ("photo", "Photos"),
    ("pills", "Pills"),
    ("I'm stuck", "Get help"),
])
def test_runs_the_right_shortcut(said, expected):
    assert brain().hear(said).ran == expected


def test_say_action_reads_text():
    assert brain().hear("pills").reply == "Take the blue pill with breakfast."


def test_builtins():
    b = brain()
    assert b.hear("what time is it").reply.startswith("It's ")
    listed = b.hear("what can I say").reply
    assert "Email" in listed and "Mary" in listed and ", or Luca" in listed
    assert b.runner.log == []


def test_did_you_mean_yes_and_no():
    b = brain()
    r = b.hear("foto")
    assert r.ran == "" and r.reply == "Did you mean Photos?"
    assert b.hear("yes").ran == "Photos"
    b.hear("foto")
    assert b.hear("no").ran == "" and b.pending is None


def test_nonsense_is_not_run():
    b = brain()
    r = b.hear("the cat sat quietly upstairs")
    assert r.ran == "" and not r.question and b.runner.log == []


# ---- requests with something in them ------------------------------------------

@pytest.mark.parametrize("said, url", [
    ("open a new email and send to Mary", "https://mail.google.com/mail/?view=cm&fs=1&to=mary%40example.com"),
    ("email my daughter about Sunday lunch please",
     "https://mail.google.com/mail/?view=cm&fs=1&to=mary%40example.com&su=Sunday+lunch"),
    ("go on google and search cheap flights to Rome", "https://www.google.com/search?q=cheap+flights+to+Rome"),
    ("search for New York hotels", "https://www.google.com/search?q=New+York+hotels"),
    ("look up recipes for ragù", "https://www.google.com/search?q=recipes+for+rag%C3%B9"),
    ("search for photos of Rome", "https://www.google.com/search?q=photos+of+Rome"),
    ("can you play Pavarotti on YouTube", "https://www.youtube.com/results?search_query=Pavarotti"),
    ("youtube cats", "https://www.youtube.com/results?search_query=cats"),
    ("how do I get to the hospital", "https://www.google.com/maps/dir/?api=1&destination=the+hospital"),
    ("what's the weather like", "https://www.google.com/search?q=weather"),
    ("call Marco", "whatsapp://send?phone=393331234567"),
    ("whatsapp Marco saying I'll be late", "whatsapp://send?phone=393331234567&text=I%27ll+be+late"),
    ("send a message to marry", "whatsapp://send?phone=61412345678"),
    ("video call Luca", "https://meet.example.com/luca"),
])
def test_requests_go_to_the_right_screen(said, url):
    b = brain()
    r = b.hear(said)
    assert r.ran, r
    assert opened(b) == url


def test_email_services():
    assert opened_for("email Mary", email_service="outlook").startswith(
        "https://outlook.live.com/mail/0/deeplink/compose?to=mary%40example.com")
    assert opened_for("email Mary about the party", email_service="mailto") == \
        "mailto:mary@example.com?subject=the%20party"
    assert opened_for("message Marco", messaging="whatsapp_web") == \
        "https://web.whatsapp.com/send?phone=393331234567"


def opened_for(said, **extra):
    b = brain(**extra)
    b.hear(said)
    return opened(b)


def test_missing_details_are_explained():
    b = brain()
    assert "don't have an email address for Marco" in b.hear("email Marco").reply
    assert b.runner.log == []


def test_open_my_email_still_opens_the_inbox():
    b = brain()
    assert b.hear("open my email").ran == "Email" and opened(b) == "https://mail.google.com"


ITALIAN = [
    ("scrivi una email a Maria riguardo al pranzo di domenica",
     "https://mail.google.com/mail/?view=cm&fs=1&to=mary%40example.com&su=pranzo+di+domenica"),
    ("cerca voli economici per Roma", "https://www.google.com/search?q=voli+economici+per+Roma"),
    ("metti Pavarotti su YouTube", "https://www.youtube.com/results?search_query=Pavarotti"),
    ("come arrivo all'ospedale", "https://www.google.com/maps/dir/?api=1&destination=ospedale"),
    ("che tempo fa a Firenze", "https://www.google.com/search?q=meteo+Firenze"),
    ("chiama Marco", "whatsapp://send?phone=393331234567"),
    ("apri la posta", "https://mail.google.com"),
]


@pytest.mark.parametrize("said, url", ITALIAN)
def test_italian(said, url):
    b = brain("it", shortcuts=config.first_run_config("it")["shortcuts"])
    b.hear(said)
    assert opened(b) == url


def test_italian_replies_and_builtins():
    b = brain("it")
    assert b.hear("chiama Marco").reply.startswith("Ecco Marco.")
    assert b.hear("che ore sono").reply.startswith("Sono le ")
    assert b.hear("cosa posso dire").reply.startswith("Puoi dire: ")


# ---- AI helper (no network: a fake stands in) ----------------------------------

def test_ai_used_only_when_unsure():
    class FakeAI:
        calls = []

        def handle(self, said, b):
            self.calls.append(said)
            return b.run_shortcut("Photos")

    b = brain()
    b.assistant = FakeAI()
    assert b.hear("open my email").ran == "Email"
    assert b.hear("search for pasta").ran
    assert FakeAI.calls == []
    assert b.hear("I'd love to look at the little ones from Christmas").ran == "Photos"
    assert len(FakeAI.calls) == 1


def test_ai_failure_falls_back():
    class Broken:
        def handle(self, said, b):
            raise RuntimeError("no internet")

    b = brain()
    b.assistant = Broken()
    assert "didn't understand" in b.hear("the cat sat quietly upstairs").reply


def test_yes_or_no():
    en, it = i18n.get("en"), i18n.get("it")
    assert matcher.yes_or_no("yes please", en) == "yes"
    assert matcher.yes_or_no("no not that", en) == "no"
    assert matcher.yes_or_no("open the photos", en) is None
    assert matcher.yes_or_no("sì", it) == "yes"
    assert matcher.yes_or_no("lascia stare", it) == "no"


# ---- the local server ----------------------------------------------------------

@pytest.fixture
def server(tmp_path):
    path = tmp_path / "config.json"
    config.save({"shortcuts": SHORTCUTS, "contacts": CONTACTS}, path)
    s = AiutaServer(port=0, cfg_path=path, runner=actions.Runner(dry_run=True))
    s.start()
    yield s
    s.stop()


def call(server, path, body=None, key=True):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-Aiuta-Key"] = server.key
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"http://127.0.0.1:{server.port}{path}", data=data, headers=headers)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_pages_need_the_key(server):
    assert call(server, "/", key=False)[0] == 403
    assert call(server, "/setup", key=False)[0] == 403
    assert call(server, "/api/ui", key=False)[0] == 403
    assert call(server, "/api/hear", {"text": "email"}, key=False)[0] == 403
    assert call(server, "/ping", key=False)[0] == 200
    status, page = call(server, f"/?key={server.key}", key=False)
    assert status == 200 and b"Press and talk" not in page  # words come from the language file
    status, page = call(server, f"/setup?key={server.key}", key=False)
    assert status == 200 and b"data-t=\"save\"" in page


def test_ui_info_and_tiles(server):
    info = json.loads(call(server, "/api/ui")[1])
    assert info["ui"]["talk"] == "Press and talk"
    labels = [t["label"] for t in info["tiles"]]
    assert "Email" in labels and "Call Mary" in labels and "Call Luca" in labels


def test_hear_and_tiles(server):
    r = json.loads(call(server, "/api/hear", {"text": "email Mary"})[1])
    assert r["ran"] == "Mary" and "new email to Mary" in r["reply"]
    r = json.loads(call(server, "/api/tile", {"kind": "contact", "name": "Marco"})[1])
    assert r["ran"] == "Marco"
    r = json.loads(call(server, "/api/tile", {"kind": "shortcut", "name": "Photos"})[1])
    assert r["ran"] == "Photos"


def test_save_and_load_settings(server):
    status, raw = call(server, "/api/config")
    data = json.loads(raw)
    assert "it" in data["languages"] and data["setup"]["save"] == "Save"
    cfg = data["config"]
    cfg.update(person_name="Nonno Gino", language="it", ai={"enabled": False, "api_key": "sk-secret"})
    assert call(server, "/api/config", cfg)[0] == 200
    got = json.loads(call(server, "/api/config")[1])
    assert got["config"]["ai"]["api_key"] == MASK  # never sent back to the page
    assert got["setup"]["save"] == "Salva"
    call(server, "/api/config", got["config"])  # saving the masked value keeps the real key
    assert config.load(server.cfg_path)["ai"]["api_key"] == "sk-secret"
    info = json.loads(call(server, "/api/ui")[1])
    assert info["lang"] == "it" and info["person_name"] == "Nonno Gino"


def test_save_rejects_bad_settings(server):
    status, raw = call(server, "/api/config", {"shortcuts": [{"name": "X", "action": "rm"}]})
    assert status == 400 and b"unknown action" in raw


def test_try_it(server):
    r = json.loads(call(server, "/api/test", {"kind": "shortcut", "item": SHORTCUTS[0]})[1])
    assert r["reply"] == "Opening Email."
    r = json.loads(call(server, "/api/test", {"kind": "contact", "how": "email", "item": CONTACTS[0]})[1])
    assert "Mary" in r["reply"]
    assert server.runner.log[-1] == ("open_website",
                                     "https://mail.google.com/mail/?view=cm&fs=1&to=mary%40example.com")


def test_example_config_is_valid():
    cfg = config.load(ROOT / "examples" / "config.example.json")
    b = Brain(cfg, runner=actions.Runner(dry_run=True))
    assert b.hear("I'm stuck").ran == "Get help"
    assert b.hear("email Harry about the photos").ran == "Harry"
    assert b.hear("put the football on").ran == "Football"


# ---- launcher ------------------------------------------------------------------

def test_window_is_an_app_window_with_its_own_profile(tmp_path):
    from aiuta import launcher
    cmd = launcher.window_command("msedge.exe", "http://127.0.0.1:1/?key=k", tmp_path)
    assert cmd[0] == "msedge.exe"
    assert "--app=http://127.0.0.1:1/?key=k" in cmd
    assert f"--user-data-dir={tmp_path}" in cmd


def test_second_launch_finds_the_running_copy(server):
    from aiuta import launcher
    assert launcher.already_running(server.port)
    assert not launcher.already_running(1)


def test_icon_is_served(server):
    status, body = call(server, "/icon.png", key=False)
    assert status == 200 and body[:4] == b"\x89PNG"
