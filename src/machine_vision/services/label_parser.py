from __future__ import annotations

import json
import re
import unicodedata
from urllib.parse import parse_qs, urlparse


WAYBILL_PATTERNS = (
    re.compile(r"\b[A-Z]{2,5}\d{7,16}\b", re.IGNORECASE),
    re.compile(r"\b\d{9,18}\b"),
)


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def find_waybill(*values: str | None) -> str | None:
    for value in values:
        if not value:
            continue
        compact = re.sub(r"[\s._-]", "", value).upper()
        for pattern in WAYBILL_PATTERNS:
            match = pattern.search(compact)
            if match:
                return match.group(0).upper()
    return None


def find_waybill_in_qr(value: str | None) -> str | None:
    """Extract common waybill fields before falling back to pattern matching."""
    if not value:
        return None
    try:
        payload = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        payload = None
    if isinstance(payload, dict):
        for key in ("waybill", "waybill_code", "tracking", "tracking_number", "ma_van_don"):
            candidate = payload.get(key)
            if candidate is not None:
                found = find_waybill(str(candidate))
                if found:
                    return found

    parsed = urlparse(value)
    if parsed.scheme and parsed.query:
        query = parse_qs(parsed.query)
        for key in ("waybill", "waybill_code", "tracking", "tracking_number", "ma_van_don"):
            for candidate in query.get(key, []):
                found = find_waybill(candidate)
                if found:
                    return found
    return find_waybill(value)
