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

DEFAULT_SLIDE_CAPTIONS = [
    "Every message tells your story…",
    "The things you love, together",
    "With all my love",
    "",
]
