from __future__ import annotations

import os
from typing import Any, Protocol


class ShipmentRepository(Protocol):
    def find_by_waybill(self, code: str) -> dict[str, Any] | None: ...


class InMemoryShipmentRepository:
    def __init__(self, records: list[dict[str, Any]] | None = None, key: str = "waybill_code"):
        self.key = key
        self.records = {str(row[key]).upper(): row for row in (records or []) if key in row}

    def find_by_waybill(self, code: str) -> dict[str, Any] | None:
        return self.records.get(code.upper())


class SupabaseShipmentRepository:
    def __init__(self, settings: dict):
        try:
            from supabase import create_client  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "supabase is not installed; install the 'database' project extra"
            ) from exc
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required")
        self.client = create_client(url, key)
        self.table = str(settings.get("table", "shipments"))
        self.column = str(settings.get("waybill_column", "waybill_code"))

    def find_by_waybill(self, code: str) -> dict[str, Any] | None:
        response = (
            self.client.table(self.table)
            .select("*")
            .eq(self.column, code)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else None

