import json
import os
import urllib.error
import urllib.request
from typing import Any


class ProdigiError(Exception):
    pass


class ProdigiClient:
    def __init__(self) -> None:
        sandbox = os.environ.get("PRODIGI_SANDBOX", "true").lower() in ("1", "true", "yes")
        self.base_url = (
            "https://api.sandbox.prodigi.com"
            if sandbox
            else "https://api.prodigi.com"
        )
        self.api_key = os.environ.get("PRODIGI_API_KEY", "")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        if not self.api_key:
            raise ProdigiError("PRODIGI_API_KEY is not configured")

        url = f"{self.base_url}{path}"
        data = None
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ProdigiError(f"Prodigi HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ProdigiError(f"Prodigi request failed: {exc}") from exc

    def quote_order(
        self,
        sku: str,
        country_code: str,
        shipping_method: str | None = None,
        copies: int = 1,
    ) -> dict:
        payload: dict[str, Any] = {
            "items": [{"sku": sku, "copies": copies}],
            "recipient": {
                "address": {"countryCode": country_code.upper()},
            },
        }
        if shipping_method:
            payload["shippingMethod"] = shipping_method
        return self._request("POST", "/v4.0/Quotes", payload)

    def create_order(self, order_payload: dict) -> dict:
        return self._request("POST", "/v4.0/Orders", order_payload)


def default_sku(orientation: str = "portrait") -> str:
    if orientation == "landscape":
        return os.environ.get(
            "PRODIGI_GREETING_CARD_SKU_LANDSCAPE",
            os.environ.get("PRODIGI_GREETING_CARD_SKU", "GLOBAL-CARD-7X5"),
        )
    return os.environ.get("PRODIGI_GREETING_CARD_SKU", "GLOBAL-CARD-5X7")


def card_price_pence() -> int:
    return int(os.environ.get("CARD_PRICE_PENCE", "1299"))
