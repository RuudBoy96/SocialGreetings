import os
from pathlib import Path
from urllib.parse import urljoin

from prodigi_client import ProdigiClient, default_sku


ASSETS_DIR_NAME = "assets"
WEBHOOK_EVENTS_DIR = "stripe_events"


def assets_dir(base_dir: Path, card_id: str) -> Path:
    path = base_dir / ASSETS_DIR_NAME / card_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def public_base_url(fallback: str) -> str:
    return os.environ.get("PUBLIC_BASE_URL", fallback).rstrip("/")


def build_asset_urls(card_id: str, page_count: int, token: str, base_url: str) -> list[dict]:
    areas = ["front", "inside", "back", "extra"]
    urls = []
    for idx in range(page_count):
        area = areas[idx] if idx < len(areas) else f"page{idx + 1}"
        urls.append({
            "printArea": area,
            "url": f"{base_url}/card/{card_id}/asset/{idx}?token={token}",
        })
    return urls


def submit_prodigi_order(
    card_data: dict,
    shipping_details: dict,
    customer_email: str | None,
    asset_urls: list[dict],
) -> str:
    client = ProdigiClient()
    sku = default_sku(card_data.get("orientation", "portrait"))
    recipient_name = shipping_details.get("name") or card_data.get("receiver_name", "Customer")
    address = shipping_details.get("address") or {}

    payload = {
        "shippingMethod": shipping_details.get("shipping_method", "Standard"),
        "recipient": {
            "name": recipient_name,
            "email": customer_email or "",
            "address": {
                "line1": address.get("line1", ""),
                "line2": address.get("line2") or "",
                "postalOrZipCode": address.get("postal_code", ""),
                "countryCode": address.get("country", "GB"),
                "townOrCity": address.get("city", ""),
                "stateOrCounty": address.get("state") or "",
            },
        },
        "items": [
            {
                "sku": sku,
                "copies": 1,
                "sizing": "fillPrintArea",
                "assets": asset_urls[:1] if len(asset_urls) == 1 else asset_urls,
            }
        ],
    }

    result = client.create_order(payload)
    order = result.get("order") or result
    order_id = order.get("id") or order.get("orderId") or ""
    if not order_id:
        raise RuntimeError(f"Unexpected Prodigi response: {result}")
    return order_id


def ensure_pdf_asset(render_pdf_fn, card_id: str, base_dir: Path) -> Path:
    out_dir = assets_dir(base_dir, card_id)
    pdf_path = out_dir / "card.pdf"
    if not pdf_path.exists():
        pdf_bytes = render_pdf_fn()
        pdf_path.write_bytes(pdf_bytes)
    return pdf_path
