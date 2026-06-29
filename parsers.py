import re
from datetime import datetime
from typing import BinaryIO, TextIO, Union

from platforms import PLATFORMS

WHATSAPP_PATTERN = re.compile(
    r"(\d{1,2}[\/\.]\d{1,2}[\/\.]\d{2,4}[, ]\s?\d{2}:\d{2}(?::\d{2})?(?:\s?[AP]M)?)"
    r"[\]\s\-]+(.*?):\s?(.*)",
    re.IGNORECASE,
)

IMESSAGE_PATTERNS = [
    re.compile(
        r"(\w+ \d{1,2}, \d{4},? \d{1,2}:\d{2}:\d{2} [AP]M) - (.*?): (.*)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(\w+ \d{1,2}, \d{4} at \d{1,2}:\d{2}:\d{2} [AP]M) - (.*?): (.*)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\[(\d{1,2}/\d{1,2}/\d{2,4},? \d{1,2}:\d{2}:\d{2} [AP]M)\] (.*?): (.*)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(\d{1,2}/\d{1,2}/\d{2,4}, \d{1,2}:\d{2} [AP]M) - (.*?): (.*)",
        re.IGNORECASE,
    ),
]

MESSENGER_PATTERNS = [
    re.compile(
        r"(\d{1,2}/\d{1,2}/\d{2,4}, \d{1,2}:\d{2} [AP]M) - (.*?): (.*)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(\d{1,2} \w+ \d{4}, \d{2}:\d{2}) - (.*?): (.*)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(\w+day, \d{1,2} \w+ \d{4} at \d{2}:\d{2}) - (.*?): (.*)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\[(\d{1,2}/\d{1,2}/\d{4}, \d{1,2}:\d{2} [AP]M)\] (.*?): (.*)",
        re.IGNORECASE,
    ),
]

PLATFORM_DETECTORS = {
    "whatsapp": WHATSAPP_PATTERN,
    "imessage": IMESSAGE_PATTERNS,
    "messenger": MESSENGER_PATTERNS,
}


def _read_lines(source: Union[str, TextIO, BinaryIO]) -> list[str]:
    if hasattr(source, "read"):
        content = source.read()
        if isinstance(content, bytes):
            content = content.decode("utf-8-sig", errors="replace")
        return content.splitlines()
    with open(source, "r", encoding="utf-8-sig") as file:
        return file.readlines()


def _parse_timestamp(raw: str) -> datetime | None:
    cleaned = raw.strip().replace(".", "/").replace(" at ", ", ")
    formats = (
        "%d/%m/%Y, %H:%M",
        "%d/%m/%Y, %H:%M:%S",
        "%m/%d/%Y, %H:%M",
        "%m/%d/%Y, %H:%M:%S",
        "%d/%m/%y, %H:%M",
        "%m/%d/%y, %H:%M",
        "%d %b %Y, %H:%M",
        "%d %B %Y, %H:%M",
        "%B %d, %Y, %H:%M:%S %p",
        "%b %d, %Y, %H:%M:%S %p",
        "%B %d, %Y at %H:%M:%S %p",
        "%b %d, %Y at %H:%M:%S %p",
        "%d %b %Y, %H:%M",
        "%A, %d %B %Y at %H:%M",
    )
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    # Strip brackets
    if cleaned.startswith("["):
        return _parse_timestamp(cleaned.strip("[]"))
    return None


def _format_time(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def detect_platform(lines: list[str]) -> str:
    sample = lines[:80]
    scores = {key: 0 for key in PLATFORMS}

    for line in sample:
        clean = line.replace("\u200e", "").strip()
        if not clean:
            continue

        if WHATSAPP_PATTERN.search(clean):
            scores["whatsapp"] += 2
        for pattern in IMESSAGE_PATTERNS:
            if pattern.match(clean):
                scores["imessage"] += 2
                break
        for pattern in MESSENGER_PATTERNS:
            if pattern.match(clean):
                scores["messenger"] += 2
                break

        lower = clean.lower()
        if "whatsapp" in lower or " is a contact" in lower:
            scores["whatsapp"] += 3
        if "imessage" in lower or "sent an apple cash" in lower:
            scores["imessage"] += 2
        if "messenger" in lower or "sent a photo" in lower or "sent an attachment" in lower:
            scores["messenger"] += 1

    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "whatsapp"


def _try_match_line(line: str, platform: str):
    if platform == "whatsapp":
        match = WHATSAPP_PATTERN.search(line)
        if match:
            return match.group(1), match.group(2), match.group(3)
        return None

    patterns = IMESSAGE_PATTERNS if platform == "imessage" else MESSENGER_PATTERNS
    for pattern in patterns:
        match = pattern.match(line)
        if match:
            return match.group(1), match.group(2), match.group(3)
    return None


def parse_chat_export(
    source: Union[str, TextIO, BinaryIO],
    platform: str = "auto",
) -> tuple[list[dict], str]:
    lines = _read_lines(source)
    resolved_platform = detect_platform(lines) if platform == "auto" else platform

    if resolved_platform not in PLATFORMS:
        resolved_platform = "whatsapp"

    messages = []
    current = None

    for line in lines:
        clean_line = line.replace("\u200e", "").strip()
        if not clean_line:
            continue
        if resolved_platform == "whatsapp" and (
            " is a contact" in clean_line
            or clean_line.startswith("Messages and calls are end-to-end")
        ):
            continue

        matched = _try_match_line(clean_line, resolved_platform)
        if matched:
            if current:
                messages.append(current)
            timestamp, sender, message_text = matched
            current = {
                "timestamp": timestamp.strip(),
                "sender": sender.strip(),
                "message": message_text.strip(),
            }
        elif current:
            current["message"] += f" {clean_line}"

    if current:
        messages.append(current)

    return messages, resolved_platform


def extract_contact_name(filename: str, platform: str = "auto") -> str | None:
    patterns = [
        r"WhatsApp Chat with (.+)\.txt$",
        r"iMessage Chat with (.+)\.txt$",
        r"Messages - (.+)\.txt$",
        r"Facebook Message History with (.+)\.txt$",
        r"Messenger Chat with (.+)\.txt$",
        r"(.+?) chat\.txt$",
    ]
    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def detect_participants(messages: list[dict]) -> list[str]:
    senders = []
    for msg in messages:
        name = msg["sender"]
        if name not in senders:
            senders.append(name)
    return senders


def enrich_message(msg: dict) -> dict:
    parsed = _parse_timestamp(msg["timestamp"])
    return {
        **msg,
        "sort_key": parsed.timestamp() if parsed else 0,
        "time_display": _format_time(parsed) if parsed else msg["timestamp"].split(",")[-1].strip()[:5],
        "date_key": parsed.strftime("%Y-%m-%d") if parsed else "unknown",
        "date_display": parsed.strftime(f"%A, {parsed.day} %B %Y") if parsed else "Unknown date",
    }
