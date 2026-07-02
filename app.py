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
from fulfillment import (
    assets_dir,
    build_asset_urls,
    ensure_pdf_asset,
    submit_prodigi_order,
)
from order_tokens import clean_access_token, verify_token
from parsers import detect_participants, extract_contact_name, parse_chat_export
from platforms import (
    DEFAULT_SLIDE_CAPTIONS,
    DEFAULT_INSIDE_COLOR,
    INSIDE_FONTS,
    INSIDE_FONT_SIZES,
    INSIDE_MESSAGE_PRESETS,
    INSIDE_TEXT_COLORS,
    INSIDE_ZONE_IDS,
    ORIENTATIONS,
    PLATFORMS,
    default_inside_zones,
    normalize_inside_zones,
)
from prodigi_client import ProdigiClient, ProdigiError, card_price_pence, default_sku

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "socialgreetings-dev-key")

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
GENERATED_DIR = BASE_DIR / "generated"
STRIPE_EVENTS_DIR = GENERATED_DIR / "stripe_events"
ALLOWED_EXTENSIONS = {"txt"}

RETENTION_SECONDS = 30 * 60
PAID_RETENTION_SECONDS = 7 * 24 * 60 * 60
RETENTION_MINUTES = RETENTION_SECONDS // 60
PAID_RETENTION_DAYS = PAID_RETENTION_SECONDS // 86400

UPLOAD_DIR.mkdir(exist_ok=True)
GENERATED_DIR.mkdir(exist_ok=True)
STRIPE_EVENTS_DIR.mkdir(exist_ok=True)

try:
    import stripe

    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
except ImportError:
    stripe = None


def _card_cipher() -> Fernet:
    passphrase = os.environ.get("CARD_DATA_KEY") or app.secret_key or "socialgreetings-dev-key"
    key = base64.urlsafe_b64encode(hashlib.sha256(passphrase.encode("utf-8")).digest())
    return Fernet(key)


CARD_CIPHER = _card_cipher()


@app.context_processor
def inject_card_editor_constants():
    return {
        "inside_fonts": INSIDE_FONTS,
        "inside_font_sizes": INSIDE_FONT_SIZES,
        "inside_text_colors": INSIDE_TEXT_COLORS,
        "inside_presets": INSIDE_MESSAGE_PRESETS,
    }


WATERMARK_CSS = """
.preview-watermark-layer,
.card-page.has-preview-watermark::after {
    content: "";
    position: absolute;
    inset: 0;
    z-index: 50;
    pointer-events: none;
    background-image: repeating-linear-gradient(
        -35deg,
        transparent,
        transparent 48px,
        rgba(201, 123, 132, 0.07) 48px,
        rgba(201, 123, 132, 0.07) 49px
    );
}
.preview-watermark-layer::before,
.card-page.has-preview-watermark::before {
    content: "SocialGreetings · Preview";
    position: absolute;
    inset: 0;
    z-index: 51;
    pointer-events: none;
    display: flex;
    align-items: center;
    justify-content: center;
    font: 700 1.35rem/1.2 system-ui, sans-serif;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: rgba(201, 123, 132, 0.28);
    transform: rotate(-28deg);
    white-space: nowrap;
}
.card-page { position: relative; }
"""


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def card_page_count(card_data: dict) -> int:
    if card_data.get("split_pages"):
        things = card_data.get("things", [])
        each_other = card_data.get("each_other", [])
        if things and each_other:
            return 4
    return 3


def resolve_show_watermark(card_data: dict, card_id: str) -> bool:
    if card_data.get("paid"):
        token = request.args.get("token")
        paid_at = card_data.get("paid_at", "")
        if request.args.get("clean") == "1" and verify_token(card_id, "clean", paid_at, token):
            return False
        return False
    return True


def stripe_configured() -> bool:
    return stripe is not None and bool(os.environ.get("STRIPE_SECRET_KEY"))


def render_card_pdf(page_url: str, orientation: str, *, show_watermark: bool = False) -> bytes:
    from playwright.sync_api import sync_playwright

    width, height = ("7in", "5in") if orientation == "landscape" else ("5in", "7in")
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        try:
            page = browser.new_page()
            page.goto(page_url, wait_until="networkidle")
            page.wait_for_timeout(1200)
            extra_css = (
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
            )
            if show_watermark:
                extra_css += WATERMARK_CSS
            page.add_style_tag(content=extra_css)
            return page.pdf(
                print_background=True,
                prefer_css_page_size=True,
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            )
        finally:
            browser.close()


def render_card_page_png(page_url: str, slide_index: int, orientation: str) -> bytes:
    from playwright.sync_api import sync_playwright

    width_px = 1500 if orientation == "portrait" else 2100
    height_px = 2100 if orientation == "portrait" else 1500
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        try:
            page = browser.new_page(viewport={"width": width_px, "height": height_px})
            page.goto(page_url, wait_until="networkidle")
            page.wait_for_timeout(2500)
            slides = page.query_selector_all(".card-viewer-slide")
            target_slide = slides[slide_index] if slide_index < len(slides) else None
            card_page = target_slide.query_selector(".card-page") if target_slide else None
            if not card_page:
                card_page = page.query_selector(".card-page")
            if not card_page:
                raise RuntimeError("Card page element not found for asset render")
            return card_page.screenshot(type="png")
        finally:
            browser.close()


def _card_path(card_id: str) -> Path:
    return GENERATED_DIR / f"{card_id}.json"


def _card_expires_at(data: dict) -> datetime | None:
    expires_raw = data.get("expires_at")
    if not expires_raw:
        return None
    try:
        expires = datetime.fromisoformat(expires_raw.replace("Z", "+00:00"))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires
    except ValueError:
        return None


def _is_expired(path: Path) -> bool:
    try:
        token = path.read_bytes()
        raw = CARD_CIPHER.decrypt(token)
        data = json.loads(raw.decode("utf-8"))
        expires = _card_expires_at(data)
        if expires:
            return expires <= utc_now()
    except (InvalidToken, ValueError, json.JSONDecodeError, OSError):
        pass
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
    asset_root = GENERATED_DIR / "assets" / card_id
    if asset_root.exists():
        for f in asset_root.iterdir():
            f.unlink(missing_ok=True)
        asset_root.rmdir()


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

    expires = _card_expires_at(data)
    if expires and expires <= utc_now():
        delete_card_data(card_id)
        return None

    data.setdefault("paid", False)
    data["inside_zones"] = normalize_inside_zones(data)
    return data


def save_card_data(card_id: str, data: dict, *, refresh_expiry: bool = True) -> None:
    now = utc_now()
    data.setdefault("created_at", now.isoformat())
    data.setdefault("paid", False)
    if refresh_expiry:
        retention = PAID_RETENTION_SECONDS if data.get("paid") else RETENTION_SECONDS
        data["expires_at"] = (now + timedelta(seconds=retention)).isoformat()
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    _card_path(card_id).write_bytes(CARD_CIPHER.encrypt(raw))


def mark_card_paid(card_id: str, stripe_session_id: str) -> dict | None:
    card_data = load_card_data(card_id)
    if not card_data:
        return None
    if card_data.get("paid"):
        return card_data
    now = utc_now()
    card_data["paid"] = True
    card_data["paid_at"] = now.isoformat()
    card_data["stripe_session_id"] = stripe_session_id
    save_card_data(card_id, card_data)
    return card_data


def stripe_event_processed(event_id: str) -> bool:
    return (STRIPE_EVENTS_DIR / f"{event_id}.done").exists()


def mark_stripe_event_processed(event_id: str) -> None:
    (STRIPE_EVENTS_DIR / f"{event_id}.done").write_text("ok", encoding="utf-8")


def app_base_url() -> str:
    explicit = os.environ.get("PUBLIC_BASE_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    try:
        return request.host_url.rstrip("/")
    except RuntimeError:
        return "http://localhost:5000"


def card_render_url(card_id: str, *, clean: bool = False, watermark: bool = False, slide: int | None = None) -> str:
    base = app_base_url()
    url = urljoin(base + "/", url_for("view_card", card_id=card_id))
    params = ["pdf=1"]
    if clean:
        params.append("clean=1")
    elif watermark:
        params.append("watermark=1")
    card_data = load_card_data(card_id)
    if clean and card_data and card_data.get("paid_at"):
        token = clean_access_token(card_data)
        if token:
            params.append(f"token={token}")
    if slide is not None:
        params.append(f"render_slide={slide}")
    return url + "?" + "&".join(params)


def fulfill_paid_order(card_id: str, session: dict) -> None:
    card_data = load_card_data(card_id)
    if not card_data or not card_data.get("paid"):
        return
    if card_data.get("prodigi_order_id"):
        return

    token = clean_access_token(card_data)
    if not token:
        return

    base = app_base_url()
    page_count = card_page_count(card_data)
    orientation = card_data.get("orientation", "portrait")

    def _render_clean_pdf() -> bytes:
        return render_card_pdf(
            card_render_url(card_id, clean=True),
            orientation,
            show_watermark=False,
        )

    ensure_pdf_asset(_render_clean_pdf, card_id, GENERATED_DIR)

    for idx in range(page_count):
        slide_url = card_render_url(card_id, clean=True, slide=idx)
        png_bytes = render_card_page_png(slide_url, idx, orientation)
        out = assets_dir(GENERATED_DIR, card_id) / f"page-{idx}.png"
        out.write_bytes(png_bytes)

    asset_urls = build_asset_urls(card_id, page_count, token, base)

    shipping = session.get("shipping_details") or session.get("customer_details", {}).get("shipping") or {}
    shipping_address = shipping.get("address") or (session.get("customer_details") or {}).get("address") or {}
    customer_details = session.get("customer_details") or {}
    recipient_address = {
        "line1": shipping_address.get("line1", ""),
        "line2": shipping_address.get("line2"),
        "postal_code": shipping_address.get("postal_code", ""),
        "city": shipping_address.get("city", ""),
        "state": shipping_address.get("state"),
        "country": shipping_address.get("country", "GB"),
    }
    shipping_payload = {
        "name": shipping.get("name") or customer_details.get("name") or card_data.get("receiver_name", ""),
        "address": recipient_address,
        "shipping_method": card_data.get("selected_shipping_method", "Standard"),
    }

    try:
        order_id = submit_prodigi_order(
            card_data,
            shipping_payload,
            customer_details.get("email"),
            asset_urls,
        )
        card_data["prodigi_order_id"] = order_id
        card_data["fulfillment_status"] = "submitted"
        save_card_data(card_id, card_data, refresh_expiry=False)
    except (ProdigiError, RuntimeError) as exc:
        app.logger.exception("Prodigi fulfillment failed for card %s: %s", card_id, exc)
        card_data["fulfillment_status"] = "failed"
        card_data["fulfillment_error"] = str(exc)
        save_card_data(card_id, card_data, refresh_expiry=False)


purge_expired_cards()


@app.before_request
def _sweep_expired_cards():
    if request.path.startswith("/webhooks/"):
        return
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
        "orientation": orientation,
        "inside_zones": default_inside_zones(),
        "slide_captions": list(DEFAULT_SLIDE_CAPTIONS),
        "paid": False,
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
    return render_template(
        "privacy.html",
        retention_minutes=RETENTION_MINUTES,
        paid_retention_days=PAID_RETENTION_DAYS,
    )


@app.route("/faq")
def faq():
    return render_template("faq.html", paid_retention_days=PAID_RETENTION_DAYS)


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
        detected_platform = card_data.get("platform") or platform
        if detected_platform in ("auto", ""):
            detected_platform = platform
        card_data["platform"] = detected_platform
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
    show_watermark = resolve_show_watermark(card_data, card_id)
    clean_token = clean_access_token(card_data) if card_data.get("paid") else None
    return render_template(
        "card.html",
        card=card_data,
        inside_zones=card_data["inside_zones"],
        inside_fonts=INSIDE_FONTS,
        inside_font_sizes=INSIDE_FONT_SIZES,
        inside_text_colors=INSIDE_TEXT_COLORS,
        inside_presets=INSIDE_MESSAGE_PRESETS,
        show_watermark=show_watermark,
        clean_token=clean_token,
        paid_retention_days=PAID_RETENTION_DAYS,
    )


@app.route("/order/<card_id>")
def order_card(card_id: str):
    card_data = load_card_data(card_id)
    if not card_data:
        flash("Card not found or expired.", "error")
        return redirect(url_for("landing"))
    touch_card(card_id)

    if card_data.get("paid"):
        return redirect(url_for("order_success", card_id=card_id))

    orientation = card_data.get("orientation", "portrait")
    dims = ORIENTATIONS.get(orientation, ORIENTATIONS["portrait"])
    dim_str = f"{dims['width']} × {dims['height']}"
    page_count = card_page_count(card_data)

    return render_template(
        "order.html",
        card=card_data,
        dims=dim_str,
        page_count=page_count,
        card_price_pence=card_price_pence(),
        stripe_configured=stripe_configured(),
        prodigi_configured=ProdigiClient().configured,
    )


@app.route("/order/<card_id>/success")
def order_success(card_id: str):
    card_data = load_card_data(card_id)
    if not card_data:
        flash("Card not found or expired.", "error")
        return redirect(url_for("landing"))

    session_id = request.args.get("session_id")
    if session_id and stripe_configured() and not card_data.get("paid"):
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            session_data = session.to_dict() if hasattr(session, "to_dict") else dict(session)
            meta = session_data.get("metadata") or {}
            if session_data.get("payment_status") == "paid" and meta.get("card_id") == card_id:
                mark_card_paid(card_id, session_id)
                fulfill_paid_order(card_id, session_data)
                card_data = load_card_data(card_id) or card_data
        except Exception:
            app.logger.exception("Could not verify Stripe session for card %s", card_id)

    if not card_data.get("paid"):
        flash("Payment not completed yet.", "error")
        return redirect(url_for("order_card", card_id=card_id))
    touch_card(card_id)
    clean_token = clean_access_token(card_data)
    return render_template(
        "order_success.html",
        card=card_data,
        clean_token=clean_token,
        paid_retention_days=PAID_RETENTION_DAYS,
    )


@app.route("/order/<card_id>/cancel")
def order_cancel(card_id: str):
    flash("Checkout was cancelled. Your card is still saved — order when you're ready.", "error")
    return redirect(url_for("order_card", card_id=card_id))


@app.route("/card/<card_id>/pdf")
def card_pdf(card_id: str):
    card_data = load_card_data(card_id)
    if not card_data:
        flash("Card not found.", "error")
        return redirect(url_for("landing"))
    touch_card(card_id)

    token = request.args.get("token")
    paid_at = card_data.get("paid_at", "")
    clean_allowed = card_data.get("paid") and verify_token(card_id, "clean", paid_at, token)

    if card_data.get("paid") and not clean_allowed:
        flash("Use the download link from your order confirmation.", "error")
        return redirect(url_for("order_success", card_id=card_id))

    show_watermark = not clean_allowed
    page_url = card_render_url(card_id, clean=clean_allowed, watermark=show_watermark)
    orientation = card_data.get("orientation", "portrait")

    try:
        pdf_bytes = render_card_pdf(page_url, orientation, show_watermark=show_watermark)
    except Exception:
        app.logger.exception("PDF generation failed for card %s", card_id)
        flash("Sorry, we couldn't generate the print PDF just now. Please try again.", "error")
        return redirect(url_for("order_card", card_id=card_id))

    suffix = "preview" if show_watermark else "print"
    filename = f"socialgreetings-love-card-{suffix}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.route("/card/<card_id>/asset/<asset_id>")
def card_asset(card_id: str, asset_id: str):
    card_data = load_card_data(card_id)
    if not card_data or not card_data.get("paid"):
        return jsonify({"error": "Not found"}), 404

    token = request.args.get("token")
    paid_at = card_data.get("paid_at", "")
    if not verify_token(card_id, "clean", paid_at, token):
        return jsonify({"error": "Forbidden"}), 403

    asset_root = assets_dir(GENERATED_DIR, card_id)
    if asset_id == "pdf":
        path = asset_root / "card.pdf"
        if not path.exists():
            return jsonify({"error": "Asset not ready"}), 404
        return Response(path.read_bytes(), mimetype="application/pdf")

    if asset_id.isdigit():
        path = asset_root / f"page-{asset_id}.png"
        if not path.exists():
            return jsonify({"error": "Asset not ready"}), 404
        return Response(path.read_bytes(), mimetype="image/png")

    return jsonify({"error": "Not found"}), 404


@app.route("/api/card/<card_id>/quote", methods=["POST"])
def quote_card(card_id: str):
    card_data = load_card_data(card_id)
    if not card_data:
        return jsonify({"error": "Not found"}), 404

    payload = request.get_json(silent=True) or {}
    country = (payload.get("country") or "GB").upper()
    shipping_method = payload.get("shipping_method")

    client = ProdigiClient()
    if not client.configured:
        retail = card_price_pence()
        return jsonify({
            "configured": False,
            "country": country,
            "retail_pence": retail,
            "shipping_pence": 399,
            "total_pence": retail + 399,
            "shipping_methods": [
                {"id": "Standard", "label": "Standard delivery", "amount_pence": 399},
                {"id": "Express", "label": "Express delivery", "amount_pence": 799},
            ],
            "currency": "gbp",
            "message": "Using estimated shipping — configure PRODIGI_API_KEY for live quotes.",
        })

    sku = default_sku(card_data.get("orientation", "portrait"))
    try:
        quote = client.quote_order(sku, country, shipping_method)
    except ProdigiError as exc:
        return jsonify({"error": str(exc)}), 502

    costs = quote.get("costs") or quote.get("quotes", [{}])[0].get("costs", {})
    shipping = costs.get("shipping", {})
    items_total = costs.get("items", {})
    shipping_amount = int(float(shipping.get("amount", "0")) * 100) if isinstance(shipping.get("amount"), str) else int(shipping.get("amount", 0) * 100 if shipping.get("amount") else 399)
    print_amount = int(float(items_total.get("amount", "0")) * 100) if isinstance(items_total.get("amount"), str) else 0
    retail = card_price_pence()
    total = retail + (shipping_amount or 399)

    shipments = quote.get("shipments") or []
    methods = []
    for shipment in shipments:
        for option in shipment.get("carrier", {}).get("services", []) or []:
            methods.append({
                "id": option.get("service") or option.get("name") or "Standard",
                "label": option.get("name") or "Standard delivery",
                "amount_pence": shipping_amount or 399,
            })
    if not methods:
        methods = [
            {"id": "Standard", "label": "Standard delivery", "amount_pence": shipping_amount or 399},
        ]

    return jsonify({
        "configured": True,
        "country": country,
        "sku": sku,
        "print_cost_pence": print_amount,
        "retail_pence": retail,
        "shipping_pence": shipping_amount or methods[0]["amount_pence"],
        "total_pence": total,
        "shipping_methods": methods,
        "currency": "gbp",
    })


@app.route("/api/card/<card_id>/checkout", methods=["POST"])
def checkout_card(card_id: str):
    card_data = load_card_data(card_id)
    if not card_data:
        return jsonify({"error": "Not found"}), 404
    if card_data.get("paid"):
        return jsonify({"error": "Already paid", "success_url": url_for("order_success", card_id=card_id)}), 400

    if not stripe_configured():
        return jsonify({"error": "Stripe is not configured"}), 503

    payload = request.get_json(silent=True) or {}
    country = (payload.get("country") or "GB").upper()
    shipping_method = payload.get("shipping_method") or "Standard"
    shipping_pence = int(payload.get("shipping_pence") or 399)
    card_data["selected_shipping_method"] = shipping_method
    card_data["quote_country"] = country
    save_card_data(card_id, card_data)

    retail = card_price_pence()
    total_line = retail + shipping_pence
    base = app_base_url()

    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": "gbp",
                    "product_data": {
                        "name": "Love Messages greeting card",
                        "description": f"Printed card for {card_data.get('receiver_name', 'your recipient')}",
                    },
                    "unit_amount": total_line,
                },
                "quantity": 1,
            }
        ],
        shipping_address_collection={
            "allowed_countries": [
                "GB", "US", "CA", "AU", "IE", "FR", "DE", "ES", "IT", "NL", "BE", "SE", "NO", "DK", "NZ",
            ],
        },
        metadata={"card_id": card_id, "shipping_method": shipping_method},
        success_url=f"{base}{url_for('order_success', card_id=card_id)}?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base}{url_for('order_cancel', card_id=card_id)}",
    )
    return jsonify({"checkout_url": session.url, "session_id": session.id})


@app.route("/webhooks/stripe", methods=["POST"])
def stripe_webhook():
    if not stripe_configured():
        return jsonify({"error": "Stripe not configured"}), 503

    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    try:
        if webhook_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        else:
            event = json.loads(payload.decode("utf-8"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        sig_error = getattr(getattr(stripe, "error", None), "SignatureVerificationError", None)
        if sig_error and isinstance(exc, sig_error):
            return jsonify({"error": str(exc)}), 400
        raise

    event_id = event.get("id", "")
    if event_id and stripe_event_processed(event_id):
        return jsonify({"ok": True, "duplicate": True})

    if event.get("type") == "checkout.session.completed":
        session = event["data"]["object"]
        card_id = (session.get("metadata") or {}).get("card_id")
        if card_id:
            mark_card_paid(card_id, session.get("id", ""))
            fulfill_paid_order(card_id, session)

    if event_id:
        mark_stripe_event_processed(event_id)

    return jsonify({"ok": True})


@app.route("/api/card/<card_id>/update", methods=["POST"])
def update_card(card_id: str):
    card_data = load_card_data(card_id)
    if not card_data:
        return jsonify({"error": "Not found"}), 404

    payload = request.get_json(silent=True) or {}
    if "slide_captions" in payload:
        card_data["slide_captions"] = payload["slide_captions"]
    if "inside_zones" in payload and isinstance(payload["inside_zones"], dict):
        incoming = payload["inside_zones"]
        card_data["inside_zones"] = {
            zone_id: {
                "message": str((incoming.get(zone_id) or {}).get("message") or "")[:2000],
                "font": (incoming.get(zone_id) or {}).get("font")
                if (incoming.get(zone_id) or {}).get("font") in INSIDE_FONTS
                else "classic",
                "font_size": (incoming.get(zone_id) or {}).get("font_size")
                if (incoming.get(zone_id) or {}).get("font_size") in INSIDE_FONT_SIZES
                else "medium",
                "align": (incoming.get(zone_id) or {}).get("align")
                if (incoming.get(zone_id) or {}).get("align") in ("left", "center", "right")
                else None,
                "color": (incoming.get(zone_id) or {}).get("color")
                if (incoming.get(zone_id) or {}).get("color") in INSIDE_TEXT_COLORS
                else DEFAULT_INSIDE_COLOR,
            }
            for zone_id in INSIDE_ZONE_IDS
        }
    elif "inside_message" in payload:
        zones = normalize_inside_zones(card_data)
        zones["middle"]["message"] = str(payload.get("inside_message") or "")[:2000]
        if payload.get("inside_font") in INSIDE_FONTS:
            zones["middle"]["font"] = payload["inside_font"]
        if payload.get("inside_font_size") in INSIDE_FONT_SIZES:
            zones["middle"]["font_size"] = payload["inside_font_size"]
        card_data["inside_zones"] = zones

    card_data["inside_zones"] = normalize_inside_zones(card_data)

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
