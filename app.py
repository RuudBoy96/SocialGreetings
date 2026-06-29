import json
import os
import uuid
from pathlib import Path

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from extractor import process_chat
from parsers import detect_participants, extract_contact_name, parse_chat_export
from platforms import DEFAULT_SLIDE_CAPTIONS, INSIDE_FONTS, INSIDE_FONT_SIZES, ORIENTATIONS, PLATFORMS
from stats import AVAILABLE_STATS, compute_stats
from wordmap import compute_word_map

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "socialgreetings-dev-key")

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
GENERATED_DIR = BASE_DIR / "generated"
ALLOWED_EXTENSIONS = {"txt"}

UPLOAD_DIR.mkdir(exist_ok=True)
GENERATED_DIR.mkdir(exist_ok=True)


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def load_card_data(card_id: str) -> dict | None:
    path = GENERATED_DIR / f"{card_id}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_card_data(card_id: str, data: dict) -> None:
    path = GENERATED_DIR / f"{card_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


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

    return {
        "platform": platform,
        "orientation": orientation,
        "inside_message": form.get("inside_message", "").strip(),
        "inside_font": inside_font,
        "inside_font_size": inside_font_size,
        "slide_captions": list(DEFAULT_SLIDE_CAPTIONS),
    }


def handle_upload(form, file) -> tuple[str, Path, str, str, str]:
    filename = secure_filename(file.filename)
    card_id = str(uuid.uuid4())[:8]
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
