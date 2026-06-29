# AGENTS.md

## Cursor Cloud specific instructions

SocialGreetings is a single-service Flask web app (Python). It turns chat-export
`.txt` files (WhatsApp/iMessage/Messenger) into printable greeting cards (love /
stats / wordmap). There is no database — cards are persisted as JSON files under
`generated/` and uploads are stored temporarily in `uploads/` (both git-ignored,
auto-created at startup).

### Environment

- Dependencies are installed into a virtualenv at `.venv/` (the startup update
  script creates it and installs `requirements.txt`). Always run Python via
  `.venv/bin/python` (or activate the venv) so Flask is on the path.
- The only dependency is Flask (`requirements.txt`).

### Running the app (dev mode)

- Start: `.venv/bin/python app.py` — serves at `http://localhost:5000` with
  `debug=True` (auto-reload enabled). The port `5000` is hardcoded in `app.py`.
- There is no separate build step. `start.bat` / `build_card.bat` are
  Windows-only launchers and are not used on Linux.

### Testing / lint

- There is no test suite, lint config, or CI in this repo. To smoke-test the
  product end-to-end, start the app and POST a chat export to `/create/love`
  (or `/create/stats`, `/create/wordmap`), e.g. a WhatsApp-format file with
  lines like `15/01/2024, 09:30 - Alice: I love you ...`. A successful create
  returns a 302 redirect to `/card/<id>`.
