# Contributing to Aiuta

Thank you for helping make computers easier for the people we love.

## The one rule: features live here

Aiuta stays one project. If you build something for it (a new action, a new
language, a better voice, a phone app), send it here as a pull request
instead of keeping a private fork. The [LICENSE](LICENSE) requires this for
anyone who shares or hosts a modified version.

## What we look for

- **It's simple for the older person.** One button, big text, plain words.
  If it needs explaining, it's probably too complicated.
- **The free version stays free.** Nothing in the core may need an account
  or a subscription. Paid things (like the AI helper) must be optional and
  switched off by default.
- **Reuse what the computer already has.** Speech, voices and apps come from
  Windows and Edge; don't add heavy downloads.
- **It takes them there; they do the rest.** Aiuta opens the right screen
  (a new email to Mary, a search, a chat). Don't add anything that sends,
  clicks, deletes, pays or installs on its own.
- **Every word is translatable.** Text the person sees or says goes in
  `aiuta/locales/*.json`, never in the code.
- **It's tested.** Run `python -m pytest` and add a test for your change.

## Contributor agreement

By opening a pull request you confirm that:

1. you wrote the contribution, or have the right to give it; and
2. you give Harry Catanzariti a permanent, worldwide, royalty-free license
   to use, change and share your contribution, and to license it under the
   Aiuta Community License or any other license.

You keep the copyright to your own work.

## Getting started

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest
.venv/bin/python -m aiuta try "email Mary about lunch"
```

## Adding a language

Copy `aiuta/locales/en.json` to your language's two-letter code (e.g.
`es.json`) and translate it. Write the `filler`, `builtins`,
`contact_intents` and `query_intents` sections the way people really talk
in that language. Add a few of your own sentences to `tests/test_core.py`,
like the Italian ones, and run `python -m pytest`.
