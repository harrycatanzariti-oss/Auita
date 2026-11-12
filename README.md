# Aiuta

*From the Italian **aiutare**, "to help".*

Aiuta takes an older person where they need to go on their computer, by
voice. They press one big button and say what they want, and Aiuta opens the
right screen, ready to use:

| They say | Aiuta opens |
|---|---|
| "Email Mary about Sunday lunch" | A new email to Mary, subject "Sunday lunch". They type and press Send. |
| "Email Mary saying I'll be late" | The same, with "I'll be late" already written in |
| "Go on Google and search cheap flights to Rome" | Google results for "cheap flights to Rome" |
| "Play Pavarotti on YouTube" | YouTube results for Pavarotti |
| "How do I get to the hospital?" | The map, with directions |
| "Call Mary" / "Message Mary" | Mary's WhatsApp chat (or her video-call link) |
| "Open the photos" | The Photos app |
| "What's the weather like?" | Today's weather |
| "I'm stuck" | Remote help, so family can connect |
| "What can I say?" | Reads out everything they can ask for |

On the **free plan** Aiuta takes them to the screen, and they press Send.
On the **Basic** and **Plus** plans an AI agent does the whole task. It
always asks *"Shall I send it?"* before anything that can't be undone (see
[Plans](#plans)).

## Why it's different

- **Extremely simple.** One window: a huge **Press and talk** button, big
  picture tiles ("Email", "Photos", "Call Mary") and big text. Replies are
  read out loud. If it isn't sure, it asks *"Did you mean Photos?"* with big
  Yes / No buttons.
- **Free.** It uses the speech recognition and natural voices already
  built into Microsoft Edge on every Windows 10 and 11 computer. There's
  nothing to buy, no account and no voice software to download.
- **Any language.** Everything Aiuta says or understands lives in one
  translation file per language. English and Italian are done, and adding
  another is a translation, not new code.
- **Set up by family, from anywhere.** A family member adds the people and
  shortcuts once, sitting next to them or over RustDesk or TeamViewer.
- **An AI that does it for them, cheaply.** On the Basic plan, Amazon Nova
  does the steps on screen ("email Mary that I'll be late" → written, checked,
  sent once they say yes), at a fraction of a cent per task.

## Install on Windows (one click)

1. Download **Aiuta-Setup.exe** from the
   [latest release](https://github.com/harrycatanzariti-oss/Auita/releases/latest).
2. Double-click it.

That's it. There are no questions and no administrator password. It puts an
**Aiuta** icon on the desktop, starts with the computer, and opens straight
away.

> **"Windows protected your PC"?** The installer isn't code-signed yet, so
> Windows shows this the first time. Click **More info**, then **Run anyway**.

### First time: set it up for them

1. In Aiuta, click **Setup (for family)** in the bottom corner.
2. Choose their language, email (Gmail / Outlook / the email program) and
   WhatsApp.
3. Add **People**: name, other names they use ("my daughter"), email, and
   mobile number with country code.
4. Check the **Shortcuts**. Email, Photos, News and Calculator are already
   there. Add the websites and programs they use, and press **Try it** to check
   each one.
5. Click **Save**, then **Back to Aiuta**.
6. Press the big button once and click **Allow** when Windows asks about the
   microphone. It remembers this.

### Setting it up from far away

Connect to their computer with **RustDesk** (free, recommended),
**TeamViewer**, **AnyDesk** or **Chrome Remote Desktop**, then open
**Aiuta setup (for family)** from the Start menu.

To let them ask for help, add a **Remote help** shortcut pointing at the
remote-desktop program. When they say "I'm stuck", it opens and shows the
code they read out to you on the phone.

> **About TeamViewer:** it's only free for personal use, and it sometimes
> flags regular family support as commercial use. RustDesk has no such limit.

## How it works

```
 Aiuta window (Edge, app mode)              Aiuta.exe (runs quietly in the background)
 ┌────────────────────────────┐   words    ┌────────────────────────────────────────┐
 │  Press and talk            │ ─────────► │ understands the request                │
 │  (Edge speech recognition) │            │   "email Mary" → Gmail compose to Mary │
 │                            │ ◄───────── │ opens it in their normal browser/app   │
 │  reply read aloud          │   reply    │ (Basic/Plus) the AI agent does the steps│
 └────────────────────────────┘            └────────────────────────────────────────┘
```

- **Hearing and speaking** use Microsoft Edge's built-in speech
  recognition and voices. The Aiuta window is Edge in "app mode", with no
  address bar or tabs, using its own separate profile so their normal
  browsing is never touched. Edge's recognition uses Microsoft's online
  service, so talking needs the internet. Without it they can still press
  the tiles or type.
- **Understanding** is done on the computer, for free. It forgives
  mistakes ("e-mail", "marry" for Mary), strips filler ("can you please…"),
  and picks out the person, the search words or the place.
- **Privacy:** the setup and window only work on that computer (127.0.0.1)
  and need a secret key, so no one on the internet or the home Wi-Fi can
  reach them. Settings are one file:
  `%APPDATA%\aiuta\config.json`.

## Plans

| | **Free** | **Basic** | **Plus** |
|---|---|---|---|
| Opens apps, sites, searches, YouTube, maps | ✓ | ✓ | ✓ |
| Starts emails, WhatsApp and calls, words filled in | ✓ | ✓ | ✓ |
| Understands anything they say, answers questions | | ✓ | ✓ |
| Writes the email or message for them | | ✓ | ✓ |
| Does the steps on screen (asks before sending) | | ✓ | ✓ |
| AI | none | Amazon Nova Lite / Micro | Claude |
| Running cost (estimate, see below) | $0 | well under $1 a month | a few dollars upwards |

Simple requests ("open my email", "search for…", "what time is it") are
always handled for free on the computer, even on Basic and Plus. The AI is
only used for what the free part can't do.

### How the agent works

1. They say "email Mary that I'll be late on Sunday".
2. The agent writes a short, warm email in their voice and opens it, ready
   to send.
3. It **reads the screen as text** through Windows UI Automation, the same
   system screen readers use, and sees for example `[1] button "Send"`.
4. Aiuta asks out loud: *"Shall I send the email to Mary?"* with big **Yes**
   and **No** buttons.
5. On Yes it presses Send and says it's done.

While it works, Aiuta shrinks into a corner of the screen, showing each step
and a big red **Stop** button.

Reading the screen as text (not screenshots) is what keeps it cheap. Each
step is a few hundred words, so even Amazon Nova Micro can do it.

### Safety rules

These rules are enforced by Aiuta's own code, not by the AI, so a confused or
tricked AI can't get around them. They live in `aiuta/agent/safety.py`.

- **Asks first** before pressing anything that sends, buys, pays, deletes,
  posts, shares or installs (in many languages), and before pressing Enter
  in email or chat windows.
- **Stops completely on bank, payment and sign-in pages**, and doesn't show
  them to the AI.
- **Never types into password boxes.**
- **"Show them how" mode** (in setup) never presses anything. It tells them
  which button to press instead.
- **Warns about scams** (requests for money, gift cards, passwords or remote
  access).
- **Privacy:** on Basic and Plus, the words on screen are sent to the AI
  provider to work out what to press. Setup says this plainly.

Screen reading works on Windows. On other systems the agent can still write
and open emails, messages, searches and maps.

### Setting up Basic (Amazon Nova)

1. In an AWS account, open **Amazon Bedrock**, choose a region near them
   (e.g. `ap-southeast-2` for Australia or `eu-south-1` for Italy), and create
   a **Bedrock API key**.
2. In Aiuta setup, choose **Basic**, paste the key, choose the region and
   **Nova Lite** (or **Nova Micro**, the cheapest), and save.

### Setting up Plus (Claude)

Choose **Plus**, paste an Anthropic API key from
<https://console.anthropic.com>, and save. The model can be changed in setup.

### What it costs to run (estimates)

A typical agent task (write an email, look at the screen, press Send) is
about five AI steps, roughly 20,000-25,000 tokens in and 1,000 out. These
are estimates; real use will vary.

| AI | Price per million tokens (in / out) | Per task (est.) | 10 tasks a day, a month (est.) |
|---|---|---|---|
| Amazon Nova Micro | $0.035 / $0.14 | ~$0.001 | ~$0.30 |
| Amazon Nova Lite | $0.06 / $0.24 | ~$0.002 | ~$0.50 |
| Claude Haiku 5.5 | $0.10 / $0.50 | ~$0.003 | ~$1 |
| Claude Sonnet 5.5 | $2 / $10 | ~$0.06 | ~$18 |
| Claude Opus 5.5 (default for Plus) | $4 / $20 | ~$0.12 | ~$36 |

Nova prices are on-demand US East rates from public price lists. Check the
[Bedrock pricing page](https://aws.amazon.com/bedrock/pricing/) for your
region.

So a **$3/month Basic plan** covers the AI cost with room to spare. Today,
Basic and Plus use the family's own AWS or Anthropic key, and the family
pays the provider directly. A hosted plan, where people simply pay $3 a
month with no keys, needs an "Aiuta Cloud" relay that holds the key, counts
usage and takes payment. That is the next piece to build (see
[License and business model](#license-and-business-model)).

## Languages

Aiuta speaks **English** and **Italiano**. To add a language:

1. Copy `aiuta/locales/en.json` to e.g. `aiuta/locales/es.json`.
2. Translate the words. The `filler`, `builtins`, `contact_intents` and
   `query_intents` sections are how people *say* things, so write them the
   way people actually talk, not word for word.
3. Run `python -m pytest`. It checks no keys are missing.
4. Open a pull request.

The installer already speaks English, Italian, Spanish, French, German,
Portuguese, Dutch, Polish, Japanese and Ukrainian.

## For developers

Runs anywhere with Python 3.9+ and Edge or Chrome (Windows, macOS, Linux):

```bash
pip install -e ".[dev]"
python -m pytest
python -m aiuta                              # open Aiuta
python -m aiuta try "email Mary about lunch" # test a phrase, without opening anything
```

| File | What it does |
|---|---|
| `aiuta/intents.py` | Requests with something in them: email/message/call someone, search, YouTube, map. |
| `aiuta/matcher.py` | Works out which shortcut was meant (fuzzy, no AI). |
| `aiuta/brain.py` | Decides what to do with what was said, and what to reply. |
| `aiuta/actions.py` | Opens apps, websites, folders and links on Windows, macOS and Linux. |
| `aiuta/server.py` | The local server behind the window and the setup page. |
| `aiuta/launcher.py` | What the desktop icon runs: starts the server and opens the window. |
| `aiuta/web/` | The window (`index.html`) and the family setup page (`setup.html`). |
| `aiuta/locales/` | One file per language. |
| `aiuta/agent/` | The AI agent: `loop.py` (the steps), `tools.py`, `safety.py` (the rules), `desktop.py` (reading the screen), `nova.py` and `claude.py` (the AIs). |
| `installer/` | The Windows installer (Inno Setup), icon and build entry point. |
| `.github/workflows/windows.yml` | Tests and builds `Aiuta-Setup.exe` on every push. A tag like `v0.2.0` publishes a release. |

### Releasing a new version

On GitHub: **Actions** → **Windows installer** → **Run workflow**, type the
version (e.g. `0.3.0`), and press **Run workflow**. GitHub builds and tests
the installer on Windows and publishes a release with `Aiuta-Setup.exe`.
Pushing a tag like `v0.3.0` does the same.

## License and business model

Aiuta is **source-available** under the [Aiuta Community License](LICENSE)
(currently a draft):

- **Free** for any person, family or non-profit that doesn't charge for it.
- **Changes go back here.** Anyone who shares or hosts a modified version
  must publish their changes and offer them to this repo.
- **Hosting or selling it** (a managed service, a paid AI tier, devices or
  support bundled with it) is allowed, but 10% of the revenue goes to the
  project.

Because of the revenue share it isn't "open source" in the official
[OSI](https://opensource.org/osd) sense, even though everyone can read and
change the code.

See [CONTRIBUTING.md](CONTRIBUTING.md) to help.
