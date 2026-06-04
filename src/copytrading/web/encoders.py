"""JSON encoder helpers for the web layer.

The :class:`DecimalEncoder` exists so the rare JSON-serialized endpoint
(e.g. future chart data) can emit :class:`~decimal.Decimal` values as their
canonical string form. Per REQ-WEB-12 the panels themselves do NOT serialize
Decimals over JSON — they render HTML — so this module stays a small utility
rather than a hot path.
"""

from __future__ import annotations

import json
from decimal import Decimal


class DecimalEncoder(json.JSONEncoder):
    """Serialize :class:`~decimal.Decimal` values as strings, not floats."""

    def default(self, o: object) -> object:
        if isinstance(o, Decimal):
            return str(o)
        return super().default(o)
