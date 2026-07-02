PLATFORMS = {
    "whatsapp": {
        "id": "whatsapp",
        "name": "WhatsApp",
        "icon": "💬",
        "export_hint": "WhatsApp → chat → ⋮ → Export chat → Without media",
        "export_steps": [
            "Open WhatsApp and go to the chat you want to turn into a card.",
            "Tap the contact or group name at the top to open chat info.",
            "Scroll down and tap “Export chat”.",
            "Choose “Without media” — you only need the text.",
            "Save or email the .txt file to yourself, then upload it below.",
        ],
        "note": "On iPhone use the share button; on Android use the ⋮ menu. We only need the .txt file.",
    },
    "imessage": {
        "id": "imessage",
        "name": "iMessage",
        "icon": "💙",
        "export_hint": "Use an iMessage exporter app (e.g. iMazing, PhoneView) and save as .txt",
        "export_steps": [
            "iMessage has no built-in export, so use a trusted exporter on your Mac or PC.",
            "Open a tool such as iMazing or PhoneView and connect your device.",
            "Select the conversation you want and choose “Export as text”.",
            "Save it as a plain .txt file.",
            "Upload the .txt file below.",
        ],
        "note": "Exporters run on your own computer — your messages never pass through us until you upload the file.",
    },
    "messenger": {
        "id": "messenger",
        "name": "Messenger",
        "icon": "💜",
        "export_hint": "Facebook → Settings → Your information → Download → Messages",
        "export_steps": [
            "On facebook.com open Settings & privacy → Settings.",
            "Go to “Your information” → “Download your information”.",
            "Select “Messages” and request the download.",
            "When it’s ready, open the conversation and save it as a .txt file.",
            "Upload the .txt file below.",
        ],
        "note": "Downloads can take a little while for Facebook to prepare — that’s normal.",
    },
}

ORIENTATIONS = {
    "portrait": {"id": "portrait", "label": "Portrait", "width": "5in", "height": "7in"},
    "landscape": {"id": "landscape", "label": "Landscape", "width": "7in", "height": "5in"},
}

# Occasions the card is marketed and tailored for. Each occasion provides its own
# default slide captions and a suggested inside message so the generated card reads
# naturally for that celebration.
OCCASIONS = {
    "birthday": {
        "id": "birthday",
        "label": "Birthday",
        "icon": "🎂",
        "accent": "#f59e0b",
        "captions": [
            "Every message, a reason to celebrate you…",
            "All the little things we love about you",
            "Happy Birthday — with all my love",
            "",
        ],
        "inside_suggestion": "Happy Birthday! Here's to another year of moments like these.",
    },
    "anniversary": {
        "id": "anniversary",
        "label": "Anniversary",
        "icon": "💞",
        "accent": "#ec4899",
        "captions": [
            "Every message tells our story…",
            "The things we love, together",
            "Happy Anniversary — with all my love",
            "",
        ],
        "inside_suggestion": "Happy Anniversary. Every day with you is still my favourite.",
    },
}

DEFAULT_OCCASION = "birthday"

INSIDE_FONTS = {
    "classic": {"id": "classic", "label": "Classic Serif", "family": "Georgia, 'Times New Roman', serif"},
    "modern": {"id": "modern", "label": "Modern Sans", "family": "Inter, -apple-system, sans-serif"},
    "handwritten": {"id": "handwritten", "label": "Handwritten", "family": "'Caveat', cursive"},
    "elegant": {"id": "elegant", "label": "Elegant", "family": "'Playfair Display', Georgia, serif"},
    "typewriter": {"id": "typewriter", "label": "Typewriter", "family": "'Courier New', Courier, monospace"},
}

INSIDE_FONT_SIZES = {
    "small": {"id": "small", "label": "Small", "size": "14px"},
    "medium": {"id": "medium", "label": "Medium", "size": "20px"},
    "large": {"id": "large", "label": "Large", "size": "28px"},
    "xlarge": {"id": "xlarge", "label": "Extra Large", "size": "36px"},
}

INSIDE_ZONE_IDS = ("top", "middle", "bottom")

INSIDE_ALIGNMENTS = ("left", "center", "right")

DEFAULT_ZONE_ALIGN = {
    "top": "left",
    "middle": "center",
    "bottom": "center",
}

INSIDE_TEXT_COLORS = {
    "charcoal": {"id": "charcoal", "label": "Charcoal", "hex": "#2d2a26"},
    "ink": {"id": "ink", "label": "Ink black", "hex": "#1a1a1a"},
    "rose": {"id": "rose", "label": "Dusty rose", "hex": "#8f4550"},
    "burgundy": {"id": "burgundy", "label": "Burgundy", "hex": "#6b2d3a"},
    "forest": {"id": "forest", "label": "Forest", "hex": "#2d4a3e"},
    "navy": {"id": "navy", "label": "Navy", "hex": "#1e3a5f"},
    "plum": {"id": "plum", "label": "Plum", "hex": "#5c3d5c"},
    "gold": {"id": "gold", "label": "Warm gold", "hex": "#9a7b4f"},
}

DEFAULT_INSIDE_COLOR = "charcoal"

DEFAULT_INSIDE_ZONE = {
    "message": "",
    "font": "classic",
    "font_size": "medium",
    "align": "center",
    "color": DEFAULT_INSIDE_COLOR,
}


def inside_color_hex(color_id: str) -> str:
    entry = INSIDE_TEXT_COLORS.get(color_id)
    if entry:
        return entry["hex"]
    return INSIDE_TEXT_COLORS[DEFAULT_INSIDE_COLOR]["hex"]

INSIDE_MESSAGE_PRESETS = [
    {
        "id": "favourite",
        "label": "My favourite person",
        "message": "Every message reminded me why you're my favourite person.",
    },
    {
        "id": "thank_you",
        "label": "Thank you for being you",
        "message": "All these little messages add up to one big thank you for being you.",
    },
    {
        "id": "with_love",
        "label": "With all my love",
        "message": "Happy birthday — with all my love, always.",
    },
    {
        "id": "little_things",
        "label": "The little things",
        "message": "It's the little things you say that mean the most.",
    },
    {
        "id": "keepsake",
        "label": "A keepsake",
        "message": "Turned our chats into something I can hold — because you matter.",
    },
    {
        "id": "always",
        "label": "Always & forever",
        "message": "For every laugh, every late-night chat, and every 'love you' — always.",
    },
]


def default_inside_zones() -> dict:
    zones = {}
    for zone_id in INSIDE_ZONE_IDS:
        zone = dict(DEFAULT_INSIDE_ZONE)
        zone["align"] = DEFAULT_ZONE_ALIGN[zone_id]
        zones[zone_id] = zone
    return zones


def normalize_inside_zones(card_data: dict) -> dict:
    """Return inside_zones dict, migrating legacy single-field cards."""
    raw = card_data.get("inside_zones")
    if isinstance(raw, dict) and all(z in raw for z in INSIDE_ZONE_IDS):
        zones = default_inside_zones()
        for zone_id in INSIDE_ZONE_IDS:
            src = raw.get(zone_id) or {}
            align = src.get("align")
            if align not in INSIDE_ALIGNMENTS:
                align = DEFAULT_ZONE_ALIGN[zone_id]
            color = src.get("color")
            if color not in INSIDE_TEXT_COLORS:
                color = DEFAULT_INSIDE_COLOR
            zones[zone_id] = {
                "message": str(src.get("message") or ""),
                "font": src.get("font") if src.get("font") in INSIDE_FONTS else "classic",
                "font_size": src.get("font_size") if src.get("font_size") in INSIDE_FONT_SIZES else "medium",
                "align": align,
                "color": color,
            }
        return zones

    zones = default_inside_zones()
    legacy_msg = card_data.get("inside_message") or ""
    if legacy_msg:
        zones["middle"] = {
            "message": legacy_msg,
            "font": card_data.get("inside_font") if card_data.get("inside_font") in INSIDE_FONTS else "classic",
            "font_size": card_data.get("inside_font_size") if card_data.get("inside_font_size") in INSIDE_FONT_SIZES else "medium",
            "align": DEFAULT_ZONE_ALIGN["middle"],
            "color": DEFAULT_INSIDE_COLOR,
        }
    return zones


DEFAULT_SLIDE_CAPTIONS = [
    "Every message tells your story…",
    "The things you love, together",
    "With all my love",
    "",
]
