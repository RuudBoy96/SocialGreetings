# AGENTS.md

## Cursor Cloud specific instructions

SocialGreetings is a single Flask web app (Python). It turns chat exports
(WhatsApp / iMessage / Messenger `.txt` files) into printable greeting cards
(love, stats, word map). There is no separate frontend build — templates are
server-rendered Jinja, and static CSS/JS is served directly.

### Environment
- Dependencies are installed into a project virtualenv at `.venv` by the
  startup update script (`python3 -m venv .venv` + `pip install -r requirements.txt`).
  Always run Python via `.venv/bin/python` (or activate `.venv`).

### Run (development)
- Start the dev server: `.venv/bin/python app.py` — serves on
  http://localhost:5000 with Flask debug mode + auto-reload enabled.
- The `*.bat` files (`start.bat`, `build_card.bat`) are Windows-only helpers;
  do not use them here. Use `app.py` directly.

### Tests / Lint
- There is no automated test suite and no lint/format config in this repo.
  Verify changes by running the app and exercising the card flows.

### Notes
- `uploads/` and `generated/` are created automatically at startup and are
  gitignored. Uploaded chat files are deleted after processing; generated
  card data persists as `generated/<card_id>.json`.
- To exercise the core flow you need a chat export `.txt`. The create pages
  (`/create/love`, `/create/stats`, `/create/wordmap`) accept only `.txt`
  uploads. A simple WhatsApp-style line is:
  `12/01/2024, 09:15 - Sam: I love you so much` (love cards filter for
  "love" messages, so include several to get a non-empty card).
