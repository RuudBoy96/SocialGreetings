import re
from datetime import datetime
from typing import BinaryIO, TextIO, Union

from parsers import (
    detect_participants,
    enrich_message as _enrich_base,
    extract_contact_name,
    parse_chat_export,
)

# Re-export for backwards compatibility
parse_whatsapp_export = lambda source: parse_chat_export(source, "whatsapp")[0]

EXCLUDE_PHRASES = [
    "would love", "i'd love", "id love", "if you'd love", "you'd love",
    "love to", "love it", "love this", "love that", "love the pic",
    "love the photo", "love these", "love those",
    "lovely", "with love", "lots of love", "sending love",
    "make love", "making love", "love island",
    "don't love", "didn't love", "not sure i love",
    "sad", "conflicting", "triggering", "bummer", "pity", "pain",
]

EACH_OTHER_PATTERNS = [
    re.compile(r"\blove\s+you\b", re.IGNORECASE),
    re.compile(r"\blove\s+u\b", re.IGNORECASE),
    re.compile(r"\bi\s+love\s+you\b", re.IGNORECASE),
    re.compile(r"\blove\s+how\s+you\b", re.IGNORECASE),
    re.compile(r"\blove\s+that\s+you\b", re.IGNORECASE),
    re.compile(r"\blove\s+your\b", re.IGNORECASE),
    re.compile(r"\blove\s+being\s+with\s+you\b", re.IGNORECASE),
    re.compile(r"\blove\s+spending\s+time\s+with\s+you\b", re.IGNORECASE),
]

THINGS_PATTERNS = [
    re.compile(r"\bi\s+love\s+(?:the\s+|my\s+|our\s+)?[a-z]", re.IGNORECASE),
    re.compile(r"\blove\s+(?:going|eating|looking|watching|visiting|having)\b", re.IGNORECASE),
    re.compile(
        r"\blove\s+(?:mornings?|dinners?|food|stars?|rain|thunderstorms?|parks?|"
        r"restaurants?|coffee|music|films?|movies?|walks?|travelling?|traveling?)\b",
        re.IGNORECASE,
    ),
]

MAX_WORDS = 40
MIN_WORDS = 3
MIN_SCORE = 2


def _parse_timestamp(raw: str) -> datetime | None:
    from parsers import _parse_timestamp as pt
    return pt(raw)


def _format_date_separator(dt: datetime) -> str:
    return dt.strftime(f"%A, {dt.day} %B %Y")


def _format_time(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def score_message(text: str) -> int:
    lower = text.lower()
    score = 0

    if not re.search(r"\blove\b", lower):
        return -10

    for pattern in EACH_OTHER_PATTERNS:
        if pattern.search(lower):
            score += 3

    for pattern in THINGS_PATTERNS:
        if pattern.search(lower):
            score += 2

    if re.search(r"\bi\s+love\b", lower):
        score += 2

    if re.search(r"\blove\s+[a-z]{3,}\b", lower):
        score += 1

    for phrase in EXCLUDE_PHRASES:
        if phrase in lower:
            score -= 3

    if re.search(r"\blove\s+it\b|\blove\s+this\b|\blove\s+that\b", lower):
        score -= 3

    if re.search(r"\blovely\b|\bloving\b|\bloved\b", lower):
        score -= 2

    return score


def categorize_message(text: str) -> str:
    lower = text.lower()
    for pattern in EACH_OTHER_PATTERNS:
        if pattern.search(lower):
            return "each_other"
    return "things"


def is_valid_message(msg: dict) -> bool:
    text = msg["message"]
    words = text.split()
    if len(words) < MIN_WORDS or len(words) > MAX_WORDS:
        return False
    if "<media omitted>" in text.lower():
        return False
    return score_message(text) >= MIN_SCORE


def enrich_message(msg: dict) -> dict:
    parsed = _parse_timestamp(msg["timestamp"])
    base = _enrich_base(msg)
    return {
        **base,
        "score": score_message(msg["message"]),
        "category": categorize_message(msg["message"]),
    }


def process_chat(
    source: Union[str, TextIO, BinaryIO],
    receiver_name: str | None = None,
    contact_name: str | None = None,
    platform: str = "auto",
) -> dict:
    """Full pipeline: parse, filter, sort, and package card data."""
    raw_messages, resolved_platform = parse_chat_export(source, platform)
    participants = detect_participants(raw_messages)

    if not receiver_name and len(participants) == 2:
        receiver_name = participants[0]

    if not contact_name and receiver_name and len(participants) == 2:
        contact_name = next((p for p in participants if p != receiver_name), participants[-1])
    elif not contact_name and participants:
        contact_name = participants[0]

    filtered = [enrich_message(msg) for msg in raw_messages if is_valid_message(msg)]
    filtered.sort(key=lambda m: m["sort_key"])

    things = [m for m in filtered if m["category"] == "things"]
    each_other = [m for m in filtered if m["category"] == "each_other"]

    return {
        "receiver_name": receiver_name or "",
        "contact_name": contact_name or "Chat",
        "participants": participants,
        "platform": resolved_platform,
        "messages": filtered,
        "things": things,
        "each_other": each_other,
        "total_count": len(filtered),
        "things_count": len(things),
        "each_other_count": len(each_other),
    }


def process_chat_file(file_path: str, receiver_name: str | None = None, contact_name: str | None = None) -> dict:
    return process_chat(file_path, receiver_name=receiver_name, contact_name=contact_name)


if __name__ == "__main__":
    import json

    file_name = "WhatsApp Chat with Kim Butler.txt"
    output_file = "extracted_messages.json"

    print("Extracting and filtering messages...")
    result = process_chat_file(file_name, receiver_name="Kim Butler")

    if result["messages"]:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result["messages"], f, indent=4, ensure_ascii=False)
        print(
            f"Success! Saved {result['total_count']} messages "
            f"({result['things_count']} things, {result['each_other_count']} each other) "
            f"to '{output_file}'."
        )
    else:
        print("No messages survived the filter.")

    input("\nPress Enter to exit...")
