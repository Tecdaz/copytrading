"""Tests for JSON encoder that serializes Decimal as string (REQ-WEB-12)."""

from __future__ import annotations

import json
from decimal import Decimal

from copytrading.web.encoders import DecimalEncoder


class TestDecimalEncoder:
    def test_serializes_decimal_as_string(self) -> None:
        # Pre-condition: encoder round-trips a single Decimal value as a string
        # and never falls back to the stdlib default (which would raise TypeError).
        payload = {"equity": Decimal("200.50")}

        rendered = json.dumps(payload, cls=DecimalEncoder)

        assert rendered == '{"equity": "200.50"}'
        # Round-trip confirms it is JSON, not a string-literal '{"equity": "200.50"}'
        parsed = json.loads(rendered)
        assert parsed == {"equity": "200.50"}
        assert isinstance(parsed["equity"], str)

    def test_serializes_list_of_decimals_as_list_of_strings(self) -> None:
        # Triangulation: a list path takes a different code path inside
        # json.JSONEncoder (it iterates internally), so we MUST verify it.
        payload = [Decimal("1.23"), Decimal("4.56")]

        rendered = json.dumps(payload, cls=DecimalEncoder)

        assert rendered == '["1.23", "4.56"]'
        parsed = json.loads(rendered)
        assert parsed == ["1.23", "4.56"]
        assert all(isinstance(x, str) for x in parsed)
