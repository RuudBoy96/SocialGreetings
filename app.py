import base64
import hashlib
import json
import os
import secrets
import time
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from extractor import process_chat
from parsers import detect_participants, extract_contact_name, parse_chat_export
from platforms import (
    DEFAULT_OCCASION,
    DEFAULT_SLIDE_CAPTIONS,
    INSIDE_FONTS,
    INSIDE_FONT_SIZES,
    OCCASIONS,
    ORIENTATIONS,
    PLATFORMS,
)
from stats import AVAILABLE_STATS, compute_stats
from wordmap import compute_word_map

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "socialgreetings-dev-key")

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
GENERATED_DIR = BASE_DIR / "generated"
ALLOWED_EXTENSIONS = {"txt"}

# Cards are deleted automatically after this much inactivity. Activity is tracked
# via the stored file's modification time, which is bumped on every view/edit/print
# and by a lightweight heartbeat while a card page is open in the browser.
RETENTION_SECONDS = 30 * 60
RETENTION_MINUTES = RETENTION_SECONDS // 60

UPLOAD_DIR.mkdir(exist_ok=True)
GENERATED_DIR.mkdir(exist_ok=True)


def _card_cipher() -> Fernet:
    """Build a Fernet cipher from CARD_DATA_KEY (any string) so stored card data is
    encrypted at rest. Falls back to the app secret for local development."""
    passphrase = os.environ.get("CARD_DATA_KEY") or app.secret_key or "socialgreetings-dev-key"
    key = base64.urlsafe_b64encode(hashlib.sha256(passphrase.encode("utf-8")).digest())
    return Fernet(key)


CARD_CIPHER = _card_cipher()


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


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
            path.unlink(missing_ok=True)


def card_exists_and_fresh(card_id: str) -> bool:
    path = _card_path(card_id)
    if not path.exists():
        return False
    if _is_expired(path):
        path.unlink(missing_ok=True)
        return False
    return True


def touch_card(card_id: str) -> None:
    path = _card_path(card_id)
    if path.exists():
        path.touch()


def delete_card_data(card_id: str) -> None:
    _card_path(card_id).unlink(missing_ok=True)


def load_card_data(card_id: str) -> dict | None:
    path = _card_path(card_id)
    if not path.exists():
        return None
    if _is_expired(path):
        path.unlink(missing_ok=True)
        return None
    try:
        token = path.read_bytes()
        raw = CARD_CIPHER.decrypt(token)
        return json.loads(raw.decode("utf-8"))
    except (InvalidToken, ValueError, json.JSONDecodeError):
        return None


def save_card_data(card_id: str, data: dict) -> None:
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    _card_path(card_id).write_bytes(CARD_CIPHER.encrypt(raw))


# Remove anything already expired when the server boots.
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
    platform = form.get("platform", "auto")
    if platform not in PLATFORMS and platform != "auto":
        platform = "auto"

    orientation = form.get("orientation", "portrait")
    if orientation not in ORIENTATIONS:
        orientation = "portrait"

    inside_font = form.get("inside_font", "classic")
    if inside_font not in INSIDE_FONTS:
        inside_font = "classic"

    inside_font_size = form.get("inside_font_size", "medium")
    if inside_font_size not in INSIDE_FONT_SIZES:
        inside_font_size = "medium"

    occasion = form.get("occasion", DEFAULT_OCCASION)
    if occasion not in OCCASIONS:
        occasion = DEFAULT_OCCASION

    slide_captions = list(OCCASIONS[occasion].get("captions") or DEFAULT_SLIDE_CAPTIONS)

    return {
        "platform": platform,
        "orientation": orientation,
        "occasion": occasion,
        "inside_message": form.get("inside_message", "").strip(),
        "inside_font": inside_font,
        "inside_font_size": inside_font_size,
        "slide_captions": slide_captions,
    }


def handle_upload(form, file) -> tuple[str, Path, str, str, str]:
    filename = secure_filename(file.filename)
    card_id = secrets.token_urlsafe(16)
    upload_path = UPLOAD_DIR / f"{card_id}_{filename}"
    file.save(upload_path)

    platform = form.get("platform", "auto")
    messages, detected_platform = parse_chat_export(str(upload_path), platform)
    resolved_platform = detected_platform if platform == "auto" else platform

    participants = detect_participants(messages)
    receiver_name, contact_name = resolve_names(form, filename, participants, resolved_platform)
    return card_id, upload_path, receiver_name, contact_name, resolved_platform


@app.route("/")
def landing():
    return render_template("landing.html", stat_options=AVAILABLE_STATS, platforms=PLATFORMS)


@app.route("/create")
def create_hub():
    return render_template("create_hub.html")


@app.route("/create/love", methods=["GET", "POST"])
def create_love():
    if request.method == "GET":
        return render_template(
            "create.html",
            platforms=PLATFORMS,
            orientations=ORIENTATIONS,
            occasions=OCCASIONS,
            inside_fonts=INSIDE_FONTS,
            inside_font_sizes=INSIDE_FONT_SIZES,
        )

    if "chat_file" not in request.files:
        flash("Please choose a chat export file.", "error")
        return redirect(url_for("create_love"))

    file = request.files["chat_file"]
    if not file or file.filename == "":
        flash("Please choose a chat export file.", "error")
        return redirect(url_for("create_love"))

    if not allowed_file(file.filename):
        flash("Only .txt chat export files are supported.", "error")
        return redirect(url_for("create_love"))

    card_id, upload_path, receiver_name, contact_name, platform = handle_upload(request.form, file)
    settings = extract_card_settings(request.form)

    try:
        split_pages = request.form.get("split_pages") == "on"
        card_data = process_chat(
            str(upload_path),
            receiver_name=receiver_name,
            contact_name=contact_name,
            platform=settings["platform"],
        )
        card_data.update(settings)
        card_data["platform"] = card_data.get("platform") or platform
        card_data["card_id"] = card_id
        card_data["card_type"] = "love"
        card_data["split_pages"] = split_pages
        card_data["original_filename"] = secure_filename(file.filename)

        if not card_data["messages"]:
            flash("No matching messages found. Try a chat with more 'love' messages.", "error")
            upload_path.unlink(missing_ok=True)
            return redirect(url_for("create_love"))

        save_card_data(card_id, card_data)
        upload_path.unlink(missing_ok=True)
        return redirect(url_for("view_card", card_id=card_id))

    except Exception as exc:
        upload_path.unlink(missing_ok=True)
        flash(f"Could not process chat file: {exc}", "error")
        return redirect(url_for("create_love"))


@app.route("/create/stats", methods=["GET", "POST"])
def create_stats():
    if request.method == "GET":
        return render_template(
            "create_stats.html",
            stat_options=AVAILABLE_STATS,
            platforms=PLATFORMS,
            orientations=ORIENTATIONS,
            occasions=OCCASIONS,
            inside_fonts=INSIDE_FONTS,
            inside_font_sizes=INSIDE_FONT_SIZES,
        )

    if "chat_file" not in request.files:
        flash("Please choose a chat export file.", "error")
        return redirect(url_for("create_stats"))

    file = request.files["chat_file"]
    if not file or file.filename == "":
        flash("Please choose a chat export file.", "error")
        return redirect(url_for("create_stats"))

    if not allowed_file(file.filename):
        flash("Only .txt chat export files are supported.", "error")
        return redirect(url_for("create_stats"))

    card_id, upload_path, receiver_name, contact_name, platform = handle_upload(request.form, file)
    settings = extract_card_settings(request.form)

    try:
        selected = request.form.getlist("stat_options")
        if not selected:
            selected = [s["id"] for s in AVAILABLE_STATS.values() if s["default"]]

        card_data = compute_stats(
            str(upload_path),
            receiver_name=receiver_name,
            contact_name=contact_name,
            selected_stats=selected,
            platform=settings["platform"],
        )
        card_data.update(settings)
        card_data["platform"] = card_data.get("platform") or platform
        card_data["card_id"] = card_id
        card_data["original_filename"] = secure_filename(file.filename)

        save_card_data(card_id, card_data)
        upload_path.unlink(missing_ok=True)
        return redirect(url_for("view_stats_card", card_id=card_id))

    except Exception as exc:
        upload_path.unlink(missing_ok=True)
        flash(f"Could not process chat file: {exc}", "error")
        return redirect(url_for("create_stats"))


@app.route("/create/wordmap", methods=["GET", "POST"])
def create_wordmap():
    if request.method == "GET":
        return render_template(
            "create_wordmap.html",
            platforms=PLATFORMS,
            orientations=ORIENTATIONS,
            occasions=OCCASIONS,
            inside_fonts=INSIDE_FONTS,
            inside_font_sizes=INSIDE_FONT_SIZES,
        )

    if "chat_file" not in request.files:
        flash("Please choose a chat export file.", "error")
        return redirect(url_for("create_wordmap"))

    file = request.files["chat_file"]
    if not file or file.filename == "":
        flash("Please choose a chat export file.", "error")
        return redirect(url_for("create_wordmap"))

    if not allowed_file(file.filename):
        flash("Only .txt chat export files are supported.", "error")
        return redirect(url_for("create_wordmap"))

    card_id, upload_path, receiver_name, contact_name, platform = handle_upload(request.form, file)
    settings = extract_card_settings(request.form)

    try:
        card_data = compute_word_map(
            str(upload_path),
            receiver_name=receiver_name,
            contact_name=contact_name,
            platform=settings["platform"],
        )
        card_data.update(settings)
        card_data["platform"] = card_data.get("platform") or platform
        card_data["card_id"] = card_id
        card_data["original_filename"] = secure_filename(file.filename)

        if not card_data["cloud_words"]:
            flash("Not enough text to build a word map. Try a longer chat export.", "error")
            upload_path.unlink(missing_ok=True)
            return redirect(url_for("create_wordmap"))

        save_card_data(card_id, card_data)
        upload_path.unlink(missing_ok=True)
        return redirect(url_for("view_wordmap_card", card_id=card_id))

    except Exception as exc:
        upload_path.unlink(missing_ok=True)
        flash(f"Could not process chat file: {exc}", "error")
        return redirect(url_for("create_wordmap"))


@app.route("/card/<card_id>")
def view_card(card_id: str):
    card_data = load_card_data(card_id)
    if not card_data:
        flash("Card not found. Please create a new one.", "error")
        return redirect(url_for("create_hub"))
    touch_card(card_id)
    card_type = card_data.get("card_type")
    if card_type == "stats":
        return redirect(url_for("view_stats_card", card_id=card_id))
    if card_type == "wordmap":
        return redirect(url_for("view_wordmap_card", card_id=card_id))
    return render_template(
        "card.html",
        card=card_data,
        inside_fonts=INSIDE_FONTS,
        inside_font_sizes=INSIDE_FONT_SIZES,
    )


@app.route("/stats/<card_id>")
def view_stats_card(card_id: str):
    card_data = load_card_data(card_id)
    if not card_data:
        flash("Stats card not found. Please create a new one.", "error")
        return redirect(url_for("create_stats"))
    touch_card(card_id)
    if card_data.get("card_type") != "stats":
        return redirect(url_for("view_card", card_id=card_id))
    return render_template(
        "stats_card.html",
        card=card_data,
        inside_fonts=INSIDE_FONTS,
        inside_font_sizes=INSIDE_FONT_SIZES,
    )


@app.route("/wordmap/<card_id>")
def view_wordmap_card(card_id: str):
    card_data = load_card_data(card_id)
    if not card_data:
        flash("Word map card not found. Please create a new one.", "error")
        return redirect(url_for("create_wordmap"))
    touch_card(card_id)
    if card_data.get("card_type") != "wordmap":
        return redirect(url_for("view_card", card_id=card_id))
    return render_template(
        "wordmap_card.html",
        card=card_data,
        inside_fonts=INSIDE_FONTS,
        inside_font_sizes=INSIDE_FONT_SIZES,
    )


@app.route("/order/<card_id>")
def order_card(card_id: str):
    card_data = load_card_data(card_id)
    if not card_data:
        flash("Card not found.", "error")
        return redirect(url_for("landing"))
    touch_card(card_id)

    orientation = card_data.get("orientation", "portrait")
    dims = ORIENTATIONS.get(orientation, ORIENTATIONS["portrait"])
    dim_str = f"{dims['width']} × {dims['height']}"

    page_count = 3
    if card_data.get("card_type") != "stats" and card_data.get("split_pages"):
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
    return jsonify({"ok": True})


@app.route("/card/<card_id>/ping", methods=["POST"])
def ping_card(card_id: str):
    """Heartbeat from an open card page: keeps the card alive while it is being viewed."""
    if not card_exists_and_fresh(card_id):
        return jsonify({"ok": False}), 404
    touch_card(card_id)
    return jsonify({"ok": True})


@app.route("/card/<card_id>/delete", methods=["POST"])
def delete_card(card_id: str):
    """Let a user delete their card and all its data on demand."""
    delete_card_data(card_id)
    if request.headers.get("X-Requested-With") or request.is_json:
        return jsonify({"ok": True})
    flash("Your card and all its data have been deleted.", "success")
    return redirect(url_for("landing"))


@app.route("/privacy")
def privacy():
    return render_template("privacy.html", retention_minutes=RETENTION_MINUTES)


@app.route("/how-to-export")
def how_to_export():
    return render_template("how_to_export.html", platforms=PLATFORMS)


@app.route("/api/preview-participants", methods=["POST"])
def preview_participants():
    if "chat_file" not in request.files:
        return jsonify({"participants": [], "contact_name": "", "platform": "whatsapp"})

    file = request.files["chat_file"]
    if not file or file.filename == "":
        return jsonify({"participants": [], "contact_name": "", "platform": "whatsapp"})

    try:
        platform = request.form.get("platform", "auto")
        messages, detected = parse_chat_export(file, platform)
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
    app.run(debug=True, port=5000)
