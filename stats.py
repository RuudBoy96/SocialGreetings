import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Union

from parsers import _parse_timestamp, detect_participants, parse_chat_export

LOVE_YOU_PATTERN = re.compile(
    r"\b(?:i\s+)?love\s+(?:you|u|ya|yah)\b|"
    r"\blove\s+you\s+(?:so\s+much|lots|loads|always|forever|xx+|xxx+)\b",
    re.IGNORECASE,
)

EMOJI_PATTERN = re.compile(
    r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
    r"\U0001F900-\U0001F9FF\U00002764-\U000027BF\u2764\ufe0f\u2665]",
)

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

AVAILABLE_STATS = {
    "total_love_you": {
        "id": "total_love_you",
        "label": "Total times you've said love you",
        "description": "Combined count of every love-you message",
        "icon": "💚",
        "default": True,
    },
    "who_says_more": {
        "id": "who_says_more",
        "label": "Who says it more",
        "description": "Which of you sends more love-you messages",
        "icon": "🏆",
        "default": True,
    },
    "peak_hour": {
        "id": "peak_hour",
        "label": "Peak hour of the day",
        "description": "The hour you're most likely to say it",
        "icon": "🕐",
        "default": True,
    },
    "monthly_trend": {
        "id": "monthly_trend",
        "label": "Love you over time",
        "description": "How your love-you messages grow month by month",
        "icon": "📈",
        "default": True,
    },
    "days_chatting": {
        "id": "days_chatting",
        "label": "Days you've been chatting",
        "description": "From first message to today in your export",
        "icon": "📅",
        "default": True,
    },
    "first_love_you": {
        "id": "first_love_you",
        "label": "First love-you moment",
        "description": "When you first said it in this chat",
        "icon": "✨",
        "default": True,
    },
    "busiest_day": {
        "id": "busiest_day",
        "label": "Busiest day of the week",
        "description": "Which day love-you messages peak",
        "icon": "📆",
        "default": False,
    },
    "top_emojis": {
        "id": "top_emojis",
        "label": "Favourite love emojis",
        "description": "Most used emojis in your love-you messages",
        "icon": "😍",
        "default": False,
    },
    "total_messages": {
        "id": "total_messages",
        "label": "Total messages sent",
        "description": "Every message in your chat history",
        "icon": "💬",
        "default": False,
    },
    "avg_per_month": {
        "id": "avg_per_month",
        "label": "Average love-yous per month",
        "description": "Your typical monthly affection rate",
        "icon": "📊",
        "default": False,
    },
    "longest_gap": {
        "id": "longest_gap",
        "label": "Longest gap between love-yous",
        "description": "The biggest pause between saying it",
        "icon": "⏳",
        "default": False,
    },
    "hourly_chart": {
        "id": "hourly_chart",
        "label": "Hourly breakdown chart",
        "description": "Visual chart of when you say it through the day",
        "icon": "📉",
        "default": True,
    },
}


def _is_love_you(text: str) -> bool:
    return bool(LOVE_YOU_PATTERN.search(text))


def _first_name(name: str) -> str:
    return name.split()[0] if name else name


def _enrich_raw(msg: dict) -> dict | None:
    parsed = _parse_timestamp(msg["timestamp"])
    if not parsed:
        return None
    return {**msg, "dt": parsed}


def compute_stats(
    source: Union[str, object],
    receiver_name: str | None = None,
    contact_name: str | None = None,
    selected_stats: list[str] | None = None,
    platform: str = "auto",
) -> dict:
    raw, resolved_platform = parse_chat_export(source, platform)
    participants = detect_participants(raw)

    if not receiver_name and participants:
        receiver_name = participants[0]

    if not contact_name and receiver_name and len(participants) == 2:
        contact_name = next((p for p in participants if p != receiver_name), participants[-1])
    elif not contact_name and participants:
        contact_name = participants[0] if participants else "Chat"

    parsed_messages = []
    for msg in raw:
        enriched = _enrich_raw(msg)
        if enriched:
            parsed_messages.append(enriched)

    parsed_messages.sort(key=lambda m: m["dt"])

    love_you_msgs = [m for m in parsed_messages if _is_love_you(m["message"])]

    if selected_stats is None:
        selected_stats = [s["id"] for s in AVAILABLE_STATS.values() if s["default"]]

    # Core aggregations
    by_sender = Counter(m["sender"] for m in love_you_msgs)
    hour_counts = Counter(m["dt"].hour for m in love_you_msgs)
    day_counts = Counter(m["dt"].weekday() for m in love_you_msgs)
    month_counts = Counter(m["dt"].strftime("%Y-%m") for m in love_you_msgs)

    emoji_counter = Counter()
    for m in love_you_msgs:
        emoji_counter.update(EMOJI_PATTERN.findall(m["message"]))

    first_dt = parsed_messages[0]["dt"] if parsed_messages else None
    last_dt = parsed_messages[-1]["dt"] if parsed_messages else None
    days_chatting = (last_dt - first_dt).days + 1 if first_dt and last_dt else 0

    first_love = love_you_msgs[0] if love_you_msgs else None

    peak_hour = hour_counts.most_common(1)[0][0] if hour_counts else None
    busiest_day_idx = day_counts.most_common(1)[0][0] if day_counts else None

    who_says_more = None
    if by_sender:
        top_sender, top_count = by_sender.most_common(1)[0]
        second_count = by_sender.most_common(2)[1][1] if len(by_sender) > 1 else 0
        who_says_more = {
            "name": top_sender,
            "short_name": _first_name(top_sender),
            "count": top_count,
            "margin": top_count - second_count,
        }

    # Monthly trend — last 14 months max for card fit
    monthly_trend = []
    if month_counts:
        sorted_months = sorted(month_counts.keys())[-14:]
        for month_key in sorted_months:
            dt = datetime.strptime(month_key, "%Y-%m")
            monthly_trend.append({
                "month": month_key,
                "label": dt.strftime("%b %Y"),
                "count": month_counts[month_key],
            })

    max_monthly = max((m["count"] for m in monthly_trend), default=1)

    # Hourly chart data (0-23)
    hourly_chart = []
    max_hourly = max(hour_counts.values()) if hour_counts else 1
    for h in range(24):
        hourly_chart.append({
            "hour": h,
            "label": f"{h:02d}:00",
            "count": hour_counts.get(h, 0),
            "pct": round((hour_counts.get(h, 0) / max_hourly) * 100) if max_hourly else 0,
        })

    # Longest gap between love-yous
    longest_gap_days = 0
    if len(love_you_msgs) >= 2:
        for i in range(1, len(love_you_msgs)):
            gap = (love_you_msgs[i]["dt"] - love_you_msgs[i - 1]["dt"]).days
            longest_gap_days = max(longest_gap_days, gap)

    months_span = len(month_counts) or 1
    avg_per_month = round(len(love_you_msgs) / months_span, 1)

    computed = {
        "card_type": "stats",
        "receiver_name": receiver_name or "",
        "contact_name": contact_name or "Chat",
        "participants": participants,
        "platform": resolved_platform,
        "selected_stats": selected_stats,
        "total_love_you": len(love_you_msgs),
        "love_you_by_person": dict(by_sender),
        "peak_hour": peak_hour,
        "peak_hour_label": f"{peak_hour:02d}:00" if peak_hour is not None else "—",
        "monthly_trend": monthly_trend,
        "max_monthly": max_monthly,
        "hourly_chart": hourly_chart,
        "max_hourly": max_hourly,
        "days_chatting": days_chatting,
        "first_chat_date": first_dt.strftime(f"%d %b %Y") if first_dt else "—",
        "first_love_you": {
            "date": first_love["dt"].strftime(f"%d %b %Y") if first_love else "—",
            "time": first_love["dt"].strftime("%H:%M") if first_love else "—",
            "sender": first_love["sender"] if first_love else "—",
            "message": first_love["message"][:80] + "…" if first_love and len(first_love["message"]) > 80 else (first_love["message"] if first_love else ""),
        },
        "busiest_day": DAY_NAMES[busiest_day_idx] if busiest_day_idx is not None else "—",
        "top_emojis": [{"emoji": e, "count": c} for e, c in emoji_counter.most_common(5)],
        "total_messages": len(parsed_messages),
        "avg_per_month": avg_per_month,
        "longest_gap_days": longest_gap_days,
        "who_says_more": who_says_more,
        "has_love_data": len(love_you_msgs) > 0,
    }

    return computed
