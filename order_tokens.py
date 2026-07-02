import hashlib
import hmac
import os
from typing import Optional


def _secret() -> str:
    return os.environ.get("SECRET_KEY", "socialgreetings-dev-key")


def make_token(card_id: str, purpose: str, paid_at: str) -> str:
    msg = f"{card_id}:{purpose}:{paid_at}".encode("utf-8")
    return hmac.new(_secret().encode("utf-8"), msg, hashlib.sha256).hexdigest()


def verify_token(card_id: str, purpose: str, paid_at: str, token: Optional[str]) -> bool:
    if not token or not paid_at:
        return False
    expected = make_token(card_id, purpose, paid_at)
    return hmac.compare_digest(expected, token)


def clean_access_token(card_data: dict) -> Optional[str]:
    if not card_data.get("paid") or not card_data.get("paid_at"):
        return None
    return make_token(card_data["card_id"], "clean", card_data["paid_at"])
