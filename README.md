# Aiuta

*From the Italian **aiutare**, "to help".*

Aiuta is a voice helper for older people who find computers hard. They press
one big button and say what they want — *"open my email"*, *"call Harry"*,
*"show me the photos"*, *"I'm stuck"* — and Aiuta opens it for them.

A family member sets it up once, choosing the handful of things their
parent or grandparent actually uses. They can do this sitting next to them,
or from the other side of the world over a remote-desktop connection.

- **Free and offline.** Speech recognition runs on the computer itself. No
  account, no subscription, no internet needed, and it runs on old machines.
- **Safe by design.** It only opens what the family set up. It never types,
  clicks, deletes, pays or installs anything on its own.
- **Forgiving.** It understands "emails", "e-mail", "can you show me my mail
  please". When it isn't sure, it asks *"Did you mean Email?"* and shows big
  Yes / No buttons.
- **Optional AI helper (paid).** Switch it on and they can talk naturally and
  ask questions ("what's a good recipe for ragù?"). It still can only open
  the family's shortcuts, and it warns about likely scams.

## What they see

One window: a large **Talk** button, a big line of text saying what's
happening, and the reply read out loud. Space bar works too. There is a small
**Setup (for family)** link in the corner.

## Built-in phrases

| They say | Aiuta does |
|---|---|
| "What can I say?" / "Help" | Reads out the list of shortcuts |
| "What time is it?" | Tells the time |
| "What day is it?" | Tells the date |
| "Yes" / "No" (also "sì") | Answers a "Did you mean…?" question |

## What a shortcut can do

| Action | Target | Example |
|---|---|---|
| Open a website | a web address | Email → `https://mail.google.com` |
| Open a program | path to the program (on Mac, the app name) | Solitaire |
| Start a call | a call link: `whatsapp://`, `facetime:`, `skype:`, `tel:` | Call Harry |
| Open a folder / file | a path | Photos → `C:\Users\Nonno\Pictures` |
| Say something | the words | Pills → "The blue pill with breakfast." |
| Remote help | path to RustDesk / TeamViewer QuickSupport / AnyDesk | "I'm stuck" |

See [`examples/config.example.json`](examples/config.example.json) for a full
example.

## Set it up

### 1. Install (one time)

You need [Python 3.9+](https://www.python.org/downloads/). On Windows, tick
"Add Python to PATH" while installing.

```bash
pip install aiuta
```

Until it's published on PyPI, install it from a copy of this repo:

```bash
pip install .
```

### 2. Download a voice model (free, ~50 MB)

Pick the small model for their language from
<https://alphacephei.com/vosk/models> (e.g. `vosk-model-small-en-us` for
English or `vosk-model-small-it` for Italian), unzip it somewhere like
`C:\Aiuta\`. You'll paste that folder's path into the setup page in step 3.

### 3. Add their shortcuts

```bash
aiuta
```

Click **Setup (for family)** in the corner. A page opens in the browser where
you add shortcuts, press **Try it** to check each one, then **Save**. The
helper picks up the changes straight away.

The settings are one file you can back up or copy to another computer:

- Windows: `%APPDATA%\aiuta\config.json`
- macOS: `~/Library/Application Support/aiuta/config.json`
- Linux: `~/.config/aiuta/config.json`

### 4. Start it when the computer starts

- Windows: press Win+R, type `shell:startup`, and put a shortcut to `aiuta`
  in that folder.
- macOS: System Settings → General → Login Items → add it.

## Setting it up from far away

Aiuta works with whichever remote-desktop tool the family already uses:

1. Connect to their computer with **RustDesk** (free and open source,
   recommended), **TeamViewer**, **AnyDesk** or **Chrome Remote Desktop**.
2. Click **Setup (for family)** on their screen and make your changes.

To let *them* ask for help, add a **Remote help** shortcut pointing at the
remote-desktop program. When they say "I'm stuck", it opens and shows the
code they read out to you on the phone.

> **About TeamViewer:** it is only free for personal use, and it sometimes
> flags regular family support as commercial use. RustDesk has no such limit,
> which is why it's the default.

The setup page is only reachable on that computer itself (127.0.0.1) and
needs a secret key that is only shown there, so nobody on the internet or the
home Wi-Fi can change it.

## The AI helper (optional)

1. `pip install "aiuta[ai]"`
2. Get an API key from <https://console.anthropic.com>.
3. In the setup page, tick **Let them talk naturally**, paste the key, and
   save.

The AI is only used when the free matcher isn't sure what they meant, so
ordinary "open my email" requests stay free. It runs Claude at low effort
with short replies to keep the cost down. You can change the model in the
setup page; a smaller model such as `claude-haiku-5-5` costs much less per
question. Without the internet, or if the key stops working, Aiuta carries on
with the free behaviour.

## Try it without a microphone

```bash
python -m aiuta try "can you show me my emails"         # shows what it would do
python -m aiuta try "can you show me my emails" --real  # actually opens it
python -m aiuta setup                                   # just the setup page
```

## For developers

| File | What it does |
|---|---|
| `aiuta/matcher.py` | Works out which shortcut was meant (fuzzy, no AI). |
| `aiuta/brain.py` | Turns what was said into a reply and an action. No UI, easy to test. |
| `aiuta/actions.py` | Opens apps, websites, folders and calls on Windows, macOS and Linux. |
| `aiuta/speech.py` | Offline listening (Vosk) and speaking (the computer's own voice). |
| `aiuta/app.py` | The big-button window (Tkinter, included with Python). |
| `aiuta/setup_server.py`, `setup.html` | The family setup page. |
| `aiuta/assistant.py` | The optional AI helper. |
| `aiuta/config.py` | Loads, checks and saves the settings file. |

```bash
pip install -e ".[dev]"
python -m pytest
```

## License and business model

Aiuta is **source-available** under the [Aiuta Community License](LICENSE)
(currently a draft):

- **Free** for any person, family or non-profit that doesn't charge for it.
- **Changes go back here.** Anyone who shares or hosts a modified version
  must publish their changes and offer them to this repo.
- **Hosting or selling it** (a managed service, a paid AI tier, devices or
  support bundled with it) is allowed, but 10% of the revenue goes to the
  project.

Because of the revenue share, it isn't "open source" in the official
[OSI](https://opensource.org/osd) sense, even though everyone can read and
change the code.

See [CONTRIBUTING.md](CONTRIBUTING.md) to help.
