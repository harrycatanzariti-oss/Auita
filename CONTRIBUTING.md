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
- **The free version stays free and offline.** Nothing in the core may need
  an account, a subscription or the internet. Paid or online things (like
  the AI helper) must be optional and switched off by default.
- **It's safe.** Aiuta only opens what a family member set up. Don't add
  anything that types, clicks, deletes, pays or installs on its own.
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
.venv/bin/python -m aiuta try "open my email"
```
