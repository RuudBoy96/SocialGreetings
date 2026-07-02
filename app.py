import base64
import hashlib
import json
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

from cryptography.fernet import Fernet, InvalidToken
from flask import Flask, Response, flash, jsonify, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from extractor import process_chat
from parsers import detect_participants, extract_contact_name, parse_chat_export
from platforms import DEFAULT_SLIDE_CAPTIONS, INSIDE_FONTS, INSIDE_FONT_SIZES, ORIENTATIONS, PLATFORMS

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "socialgreetings-dev-key")

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
GENERATED_DIR = BASE_DIR / "generated"
ALLOWED_EXTENSIONS = {"txt"}

RETENTION_SECONDS = 30 * 60
RETENTION_MINUTES = RETENTION_SECONDS // 60

UPLOAD_DIR.mkdir(exist_ok=True)
GENERATED_DIR.mkdir(exist_ok=True)


def _card_cipher() -> Fernet:
    passphrase = os.environ.get("CARD_DATA_KEY") or app.secret_key or "socialgreetings-dev-key"
    key = base64.urlsafe_b64encode(hashlib.sha256(passphrase.encode("utf-8")).digest())
    return Fernet(key)


CARD_CIPHER = _card_cipher()


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def render_card_pdf(page_url: str, orientation: str) -> bytes:
    from playwright.sync_api import sync_playwright

    width, height = ("7in", "5in") if orientation == "landscape" else ("5in", "7in")
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        try:
            page = browser.new_page()
            page.goto(page_url, wait_until="networkidle")
            page.wait_for_timeout(1200)
            page.add_style_tag(content=(
                f"@page {{ size: {width} {height}; margin: 0; }}"
                ".card-loading-overlay, .card-flat-shadow, .card-edge-sliver,"
                ".page-thumb-strip, .presenter-controls { display: none !important; }"
                ".card-viewer, .presenter-layout, .presenter-main, .presenter-stage,"
                " .carousel-viewport, .carousel-track, .card-viewer-viewport, .card-viewer-track,"
                " .card-product-scene, .card-product-wrapper, .card-flat-scene, .card-flat-wrapper {"
                " overflow: visible !important; transform: none !important;"
                " perspective: none !important; height: auto !important; min-height: 0 !important;"
                " display: block !important; padding: 0 !important; margin: 0 !important; }"
                f".carousel-slide, .card-viewer-slide {{ display: block !important; height: calc({height} - 2px) !important;"
                " min-height: 0 !important; overflow: hidden !important;"
                " padding: 0 !important; margin: 0 !important;"
                " page-break-after: always !important; break-after: page !important;"
                " break-inside: avoid !important; page-break-inside: avoid !important; }"
                ".carousel-slide:last-child, .card-viewer-slide:last-child { page-break-after: avoid !important;"
                " break-after: avoid !important; }"
                ".carousel-slide--optional:not(.is-visible),"
                ".card-viewer-slide--optional:not(.is-visible) { display: none !important; }"
                f".card-page {{ width: {width} !important; height: calc({height} - 2px) !important;"
                " max-width: none !important; min-height: 0 !important;"
                " box-sizing: border-box !important; overflow: hidden !important; }"
            ))
            return page.pdf(
                print_background=True,
                prefer_css_page_size=True,
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            )
        finally:
            browser.close()


def _card_path(card_id: str) -> Path:
    return GENERATED_DIR / f"{card_id}.json"


def _is_expired(path: Path) -> bool:
    try:
        return (time.time() - path.stat().st_mtime) > RETENTION_SECONDS
    except OSError:
        return True


def purge_expired_cards() -> None:
    for path in GENERATED_DIR.glob("*.json"):
        if _is_expired(path):
            delete_card_data(path.stem)


def card_exists_and_fresh(card_id: str) -> bool:
    path = _card_path(card_id)
    if not path.exists():
        return False
    if _is_expired(path):
        delete_card_data(card_id)
        return False
    return True


def touch_card(card_id: str) -> None:
    path = _card_path(card_id)
    if path.exists():
        path.touch()


def delete_card_data(card_id: str) -> None:
    _card_path(card_id).unlink(missing_ok=True)
    for orphan in UPLOAD_DIR.glob(f"{card_id}_*"):
        orphan.unlink(missing_ok=True)


def load_card_data(card_id: str) -> dict | None:
    path = _card_path(card_id)
    if not path.exists():
        return None
    if _is_expired(path):
        delete_card_data(card_id)
        return None
    try:
        token = path.read_bytes()
        raw = CARD_CIPHER.decrypt(token)
        data = json.loads(raw.decode("utf-8"))
    except (InvalidToken, ValueError, json.JSONDecodeError):
        return None

    expires_raw = data.get("expires_at")
    if expires_raw:
        try:
            expires = datetime.fromisoformat(expires_raw.replace("Z", "+00:00"))
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires <= utc_now():
                delete_card_data(card_id)
                return None
        except ValueError:
            pass

    return data


def save_card_data(card_id: str, data: dict) -> None:
    now = utc_now()
    data.setdefault("created_at", now.isoformat())
    data["expires_at"] = (now + timedelta(seconds=RETENTION_SECONDS)).isoformat()
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    _card_path(card_id).write_bytes(CARD_CIPHER.encrypt(raw))


purge_expired_cards()


@app.before_request
def _sweep_expired_cards():
    purge_expired_cards()


@app.after_request
def _set_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "script-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'",
    )
    return response


def resolve_names(form, filename: str, participants: list[str], platform: str = "auto") -> tuple[str, str]:
    receiver_name = form.get("receiver_name", "").strip() or form.get("card_for", "").strip()
    contact_name = form.get("contact_name", "").strip() or extract_contact_name(filename, platform) or ""

    if not receiver_name and participants:
        receiver_name = participants[0]

    if not contact_name and receiver_name and len(participants) == 2:
        contact_name = next((p for p in participants if p != receiver_name), participants[-1])
    elif not contact_name and participants:
        contact_name = participants[-1] if len(participants) > 1 else participants[0]

    return receiver_name, contact_name


def extract_card_settings(form) -> dict:
    orientation = form.get("orientation", "portrait")
    if orientation not in ORIENTATIONS:
        orientation = "portrait"

    return {
        "platform": "auto",
        "orientation": orientation,
        "inside_message": "",
        "inside_font": "classic",
        "inside_font_size": "medium",
        "slide_captions": list(DEFAULT_SLIDE_CAPTIONS),
    }


def handle_upload(form, file) -> tuple[str, Path, str, str, str]:
    filename = secure_filename(file.filename)
    card_id = secrets.token_urlsafe(16)
    upload_path = UPLOAD_DIR / f"{card_id}_{filename}"
    file.save(upload_path)

    messages, detected_platform = parse_chat_export(str(upload_path), "auto")
    participants = detect_participants(messages)
    receiver_name, contact_name = resolve_names(form, filename, participants, detected_platform)
    return card_id, upload_path, receiver_name, contact_name, detected_platform


@app.route("/")
def landing():
    return render_template("landing.html", platforms=PLATFORMS)


@app.route("/privacy")
def privacy():
    return render_template("privacy.html", retention_minutes=RETENTION_MINUTES)


@app.route("/faq")
def faq():
    return render_template("faq.html")


@app.route("/how-to-export")
def how_to_export():
    return render_template("how_to_export.html", platforms=PLATFORMS)


@app.route("/create", methods=["GET", "POST"])
def create():
    if request.method == "GET":
        return render_template(
            "create.html",
            platforms=PLATFORMS,
            orientations=ORIENTATIONS,
        )

    if "chat_file" not in request.files:
        flash("Please choose a chat export file.", "error")
        return redirect(url_for("create"))

    file = request.files["chat_file"]
    if not file or file.filename == "":
        flash("Please choose a chat export file.", "error")
        return redirect(url_for("create"))

    if not allowed_file(file.filename):
        flash("Only .txt chat export files are supported.", "error")
        return redirect(url_for("create"))

    card_id, upload_path, receiver_name, contact_name, platform = handle_upload(request.form, file)
    settings = extract_card_settings(request.form)

    try:
        card_data = process_chat(
            str(upload_path),
            receiver_name=receiver_name,
            contact_name=contact_name,
            platform="auto",
        )
        card_data.update(settings)
        card_data["platform"] = card_data.get("platform") or platform
        card_data["card_id"] = card_id
        card_data["card_type"] = "love"
        card_data["split_pages"] = False
        card_data["original_filename"] = secure_filename(file.filename)

        if not card_data["messages"]:
            flash("No matching messages found. Try a chat with more 'love' messages.", "error")
            upload_path.unlink(missing_ok=True)
            return redirect(url_for("create"))

        save_card_data(card_id, card_data)
        upload_path.unlink(missing_ok=True)
        return redirect(url_for("view_card", card_id=card_id))

    except Exception as exc:
        upload_path.unlink(missing_ok=True)
        flash(f"Could not process chat file: {exc}", "error")
        return redirect(url_for("create"))


@app.route("/create/love")
def create_love_redirect():
    return redirect(url_for("create"))


@app.route("/card/<card_id>")
def view_card(card_id: str):
    card_data = load_card_data(card_id)
    if not card_data:
        flash("Card not found or expired. Please create a new one.", "error")
        return redirect(url_for("create"))
    touch_card(card_id)
    return render_template(
        "card.html",
        card=card_data,
        inside_fonts=INSIDE_FONTS,
        inside_font_sizes=INSIDE_FONT_SIZES,
    )


@app.route("/order/<card_id>")
def order_card(card_id: str):
    card_data = load_card_data(card_id)
    if not card_data:
        flash("Card not found or expired.", "error")
        return redirect(url_for("landing"))
    touch_card(card_id)

    orientation = card_data.get("orientation", "portrait")
    dims = ORIENTATIONS.get(orientation, ORIENTATIONS["portrait"])
    dim_str = f"{dims['width']} × {dims['height']}"

    page_count = 3
    if card_data.get("split_pages"):
        things = card_data.get("things", [])
        each_other = card_data.get("each_other", [])
        if things and each_other:
            page_count = 4

    return render_template(
        "order.html",
        card=card_data,
        dims=dim_str,
        page_count=page_count,
    )


@app.route("/card/<card_id>/pdf")
def card_pdf(card_id: str):
    card_data = load_card_data(card_id)
    if not card_data:
        flash("Card not found.", "error")
        return redirect(url_for("landing"))
    touch_card(card_id)

    page_url = urljoin(request.host_url, url_for("view_card", card_id=card_id)) + "?pdf=1"
    orientation = card_data.get("orientation", "portrait")

    try:
        pdf_bytes = render_card_pdf(page_url, orientation)
    except Exception:
        app.logger.exception("PDF generation failed for card %s", card_id)
        flash("Sorry, we couldn't generate the print PDF just now. Please try again.", "error")
        return redirect(url_for("order_card", card_id=card_id))

    filename = "socialgreetings-love-card.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.route("/api/card/<card_id>/update", methods=["POST"])
def update_card(card_id: str):
    card_data = load_card_data(card_id)
    if not card_data:
        return jsonify({"error": "Not found"}), 404

    payload = request.get_json(silent=True) or {}
    if "slide_captions" in payload:
        card_data["slide_captions"] = payload["slide_captions"]
    if "inside_message" in payload:
        card_data["inside_message"] = payload["inside_message"]
    if "inside_font" in payload and payload["inside_font"] in INSIDE_FONTS:
        card_data["inside_font"] = payload["inside_font"]
    if "inside_font_size" in payload and payload["inside_font_size"] in INSIDE_FONT_SIZES:
        card_data["inside_font_size"] = payload["inside_font_size"]

    save_card_data(card_id, card_data)
    touch_card(card_id)
    return jsonify({"ok": True, "expires_at": card_data.get("expires_at")})


MAX_AVATAR_BYTES = 500 * 1024
ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp"}


@app.route("/api/card/<card_id>/avatar", methods=["POST"])
def upload_avatar(card_id: str):
    card_data = load_card_data(card_id)
    if not card_data:
        return jsonify({"error": "Not found"}), 404

    file = request.files.get("avatar")
    if not file or not file.filename:
        return jsonify({"error": "No image uploaded"}), 400

    mime = file.mimetype or ""
    if mime not in ALLOWED_AVATAR_TYPES:
        return jsonify({"error": "Image must be JPEG, PNG, or WebP"}), 400

    raw = file.read()
    if len(raw) > MAX_AVATAR_BYTES:
        return jsonify({"error": "Image must be 500 KB or smaller"}), 400

    data_url = f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
    card_data["contact_avatar"] = data_url
    save_card_data(card_id, card_data)
    touch_card(card_id)
    return jsonify({"ok": True, "contact_avatar": data_url})


@app.route("/api/card/<card_id>", methods=["DELETE"])
def api_delete_card(card_id: str):
    if not load_card_data(card_id):
        return jsonify({"error": "Not found"}), 404
    delete_card_data(card_id)
    return jsonify({"ok": True})


@app.route("/card/<card_id>/ping", methods=["POST"])
def ping_card(card_id: str):
    if not card_exists_and_fresh(card_id):
        return jsonify({"ok": False}), 404
    touch_card(card_id)
    return jsonify({"ok": True})


@app.route("/card/<card_id>/delete", methods=["POST"])
def delete_card(card_id: str):
    delete_card_data(card_id)
    if request.headers.get("X-Requested-With") or request.is_json:
        return jsonify({"ok": True})
    flash("Your card and all its data have been deleted.", "success")
    return redirect(url_for("landing"))


@app.route("/api/preview-participants", methods=["POST"])
def preview_participants():
    if "chat_file" not in request.files:
        return jsonify({"participants": [], "contact_name": "", "platform": "whatsapp"})

    file = request.files["chat_file"]
    if not file or file.filename == "":
        return jsonify({"participants": [], "contact_name": "", "platform": "whatsapp"})

    try:
        messages, detected = parse_chat_export(file, "auto")
        participants = detect_participants(messages)
        contact_name = extract_contact_name(file.filename, detected) or ""
        return jsonify({
            "participants": participants,
            "contact_name": contact_name,
            "platform": detected,
        })
    except Exception:
        return jsonify({"participants": [], "contact_name": "", "platform": "whatsapp"})


if __name__ == "__main__":
    print("SocialGreetings running at http://localhost:5000")
    app.run(debug=True, port=5000, threaded=True)
