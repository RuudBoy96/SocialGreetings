# AGENTS.md

## Cursor Cloud specific instructions

SocialGreetings is a single-service Flask web app (Python). It turns chat-export
`.txt` files (WhatsApp/iMessage/Messenger) into printable birthday/anniversary
greeting cards (love / stats / wordmap). There is no database — cards are stored
encrypted on disk under `generated/` and uploads land briefly in `uploads/` (both
git-ignored, auto-created at startup).

### Environment

- Dependencies install into a virtualenv at `.venv/` (the startup script creates it,
  installs `requirements.txt`, and runs `playwright install chromium`). Always run
  Python via `.venv/bin/python`.
- Dependencies: Flask, `cryptography` (encrypts stored cards at rest), and
  `playwright` (headless Chromium for server-side PDF rendering).

### Running the app (dev mode)

- Start: `.venv/bin/python app.py` — serves `http://localhost:5000` with `debug=True`
  and `threaded=True`. The port `5000` is hardcoded in `app.py`.
- `threaded=True` is required: the `/card/<id>/pdf` route launches headless Chromium
  which loads the card page back from this same server, so the server must handle
  concurrent requests or the PDF request deadlocks.
- There is no build step. `start.bat` / `build_card.bat` are Windows-only launchers.

### Data handling / privacy (non-obvious)

- Card data is encrypted at rest with a key derived from the `CARD_DATA_KEY` env var
  (any string). It falls back to the app secret for local dev, so set `CARD_DATA_KEY`
  (and `SECRET_KEY`) in production. If you change the key, existing `generated/*` files
  become undecryptable and are treated as not-found.
- Cards auto-delete after 30 minutes of inactivity (tracked via file mtime; bumped on
  view/edit/print and by a `POST /card/<id>/ping` heartbeat from open card pages).
  `purge_expired_cards()` runs on startup and before every request.

### Print PDF

- `GET /card/<id>/pdf` renders the card page in headless Chromium and returns a
  print-ready PDF (5x7in portrait / 7x5in landscape, one card page per sheet). The
  route injects print CSS that flattens 3D transforms/perspective on card ancestors —
  those create containing blocks that otherwise break CSS pagination into extra pages.

### Testing

- No automated test suite or linter exists. Smoke-test by starting the app and
  POSTing a chat export to `/create/love` (or `/create/stats`, `/create/wordmap`),
  e.g. a WhatsApp-format file with lines like `15/01/2024, 09:30 - Alice: I love you`.
  A successful create returns a 302 redirect to the card page.
