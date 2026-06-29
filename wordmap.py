"""Word frequency analysis for the Word Map card."""
import re
from collections import Counter

from parsers import detect_participants, parse_chat_export

WORD_PATTERN = re.compile(r"[a-zA-Z']{2,}")

STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "if", "then", "so", "as", "at", "by",
    "for", "in", "of", "on", "to", "up", "it", "is", "am", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "must", "shall", "can", "need",
    "i", "me", "my", "mine", "you", "your", "yours", "we", "us", "our", "ours",
    "they", "them", "their", "theirs", "he", "him", "his", "she", "her", "hers",
    "this", "that", "these", "those", "what", "which", "who", "whom", "whose",
    "when", "where", "why", "how", "all", "each", "every", "both", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same",
    "than", "too", "very", "just", "also", "now", "here", "there", "again",
    "once", "from", "into", "about", "after", "before", "between", "through",
    "during", "with", "without", "over", "under", "out", "off", "down", "still",
    "already", "because", "while", "though", "although", "even", "ever", "never",
    "yes", "no", "ok", "okay", "yeah", "yep", "yup", "nah", "nope", "oh", "ah",
    "um", "uh", "er", "hm", "hmm", "lol", "lmao", "omg", "tbh", "imo", "idk",
    "dont", "doesnt", "didnt", "wont", "cant", "isnt", "arent", "wasnt", "werent",
    "im", "ive", "ill", "youre", "youve", "youll", "theyre", "theyve", "theyll",
    "weve", "well", "thats", "theres", "heres", "whats", "lets", "got", "get",
    "gets", "getting", "went", "going", "gone", "come", "came", "coming", "know",
    "knew", "think", "thought", "say", "said", "says", "saying", "see", "saw",
    "seen", "want", "wanted", "like", "liked", "really", "actually", "maybe",
    "probably", "something", "anything", "everything", "nothing", "someone",
    "anyone", "everyone", "one", "two", "three", "message", "image", "omitted",
    "deleted", "media", "attached", "sticker", "missed", "call", "video",
    "audio", "document", "gif", "http", "https", "www", "com",
})

BOOST_WORDS = frozenset({
    "love", "miss", "haha", "hahaha", "always", "forever", "beautiful", "gorgeous",
    "amazing", "wonderful", "happy", "excited", "cute", "sweet", "darling", "baby",
    "babe", "honey", "heart", "kiss", "hugs", "thanks", "sorry", "please", "night",
    "morning", "dream", "together", "birthday", "anniversary", "weekend", "holiday",
    "coffee", "dinner", "home", "family", "friends", "adventure", "travel", "music",
})


def _tokenize(text: str) -> list[str]:
    words = []
    for match in WORD_PATTERN.finditer(text.lower()):
        word = match.group()
        if word in STOP_WORDS or len(word) < 2:
            continue
        if word.endswith("'s"):
            word = word[:-2]
        if word in STOP_WORDS:
            continue
        words.append(word)
    return words


def _score_word(word: str, count: int) -> float:
    boost = 1.35 if word in BOOST_WORDS else 1.0
    return count * boost


def _match_participant(name: str, participants: list[str]) -> str | None:
    if not name:
        return None
    needle = name.strip().lower()
    for participant in participants:
        pl = participant.strip().lower()
        if pl == needle or needle in pl or pl in needle:
            return participant
    return None


def _resolve_names(
    receiver_name: str,
    contact_name: str,
    participants: list[str],
) -> tuple[str, str]:
    resolved_receiver = _match_participant(receiver_name, participants)
    resolved_contact = _match_participant(contact_name, participants)

    if not resolved_receiver and participants:
        resolved_receiver = participants[0]
    if not resolved_contact and len(participants) > 1:
        resolved_contact = next(
            (p for p in participants if p != resolved_receiver),
            participants[-1],
        )
    if not resolved_receiver:
        resolved_receiver = receiver_name or "You"
    if not resolved_contact:
        resolved_contact = contact_name or "Them"
    if resolved_contact == resolved_receiver and len(participants) > 1:
        resolved_contact = next(p for p in participants if p != resolved_receiver)

    return resolved_receiver, resolved_contact


def _bucket_sender(sender: str, receiver_name: str, contact_name: str) -> str:
    if sender == receiver_name:
        return "receiver"
    if sender == contact_name:
        return "contact"
    sl = sender.lower()
    if receiver_name.lower() in sl or sl in receiver_name.lower():
        return "receiver"
    if contact_name.lower() in sl or sl in contact_name.lower():
        return "contact"
    return "other"


def compute_word_map(
    filepath: str,
    receiver_name: str,
    contact_name: str,
    platform: str = "auto",
) -> dict:
    messages, detected_platform = parse_chat_export(filepath, platform)
    participants = detect_participants(messages)
    receiver_name, contact_name = _resolve_names(receiver_name, contact_name, participants)

    receiver_counts: Counter = Counter()
    contact_counts: Counter = Counter()
    total_tokens = 0

    for msg in messages:
        sender = msg.get("sender", "")
        tokens = _tokenize(msg.get("message", ""))
        if not tokens:
            continue
        total_tokens += len(tokens)
        bucket = _bucket_sender(sender, receiver_name, contact_name)
        if bucket == "contact":
            contact_counts.update(tokens)
        else:
            receiver_counts.update(tokens)

    combined = receiver_counts + contact_counts
    if not combined:
        return {
            "card_type": "wordmap",
            "total_words": 0,
            "unique_words": 0,
            "total_messages": len(messages),
            "hero_word": None,
            "cloud_words": [],
            "shared_words": [],
            "receiver_top": [],
            "contact_top": [],
            "receiver_name": receiver_name,
            "contact_name": contact_name,
            "platform": detected_platform,
            "receiver_word_count": 0,
            "contact_word_count": 0,
        }

    shared = []
    for word, total in combined.most_common(120):
        r_count = receiver_counts.get(word, 0)
        c_count = contact_counts.get(word, 0)
        if r_count > 0 and c_count > 0:
            shared.append({
                "word": word,
                "count": total,
                "receiver_count": r_count,
                "contact_count": c_count,
                "score": _score_word(word, total),
            })

    shared.sort(key=lambda x: x["score"], reverse=True)

    if not shared:
        for word, total in combined.most_common(40):
            shared.append({
                "word": word,
                "count": total,
                "receiver_count": receiver_counts.get(word, 0),
                "contact_count": contact_counts.get(word, 0),
                "score": _score_word(word, total),
            })

    shared = shared[:40]
    hero = shared[0] if shared else None

    cloud_words = []
    for i, item in enumerate(shared):
        tier = 1 if i < 5 else (2 if i < 15 else 3)
        cloud_words.append({**item, "tier": tier})

    receiver_only = [
        {"word": w, "count": c}
        for w, c in receiver_counts.most_common(50)
        if contact_counts.get(w, 0) == 0
    ][:12]

    contact_only = [
        {"word": w, "count": c}
        for w, c in contact_counts.most_common(50)
        if receiver_counts.get(w, 0) == 0
    ][:12]

    return {
        "card_type": "wordmap",
        "total_words": total_tokens,
        "unique_words": len(combined),
        "total_messages": len(messages),
        "hero_word": hero,
        "cloud_words": cloud_words,
        "shared_words": shared[:20],
        "receiver_top": receiver_only,
        "contact_top": contact_only,
        "receiver_name": receiver_name,
        "contact_name": contact_name,
        "platform": detected_platform,
        "receiver_word_count": sum(receiver_counts.values()),
        "contact_word_count": sum(contact_counts.values()),
    }
