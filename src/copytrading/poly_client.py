"""Read-only Polymarket public API client using httpx."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import httpx

from copytrading.models import Market, Position

BASE_URL = "https://clob.polymarket.com"


class PolyClientError(Exception):
    """Raised when Polymarket API requests fail."""


class PolyClient:
    """Read-only client for Polymarket public CLOB API.

    No authentication required — all endpoints are public.
    """

    def __init__(self, base_url: str = BASE_URL, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def get_markets(self) -> list[Market]:
        """Fetch all active markets."""
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(f"{self._base_url}/markets")
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as e:
            raise PolyClientError(f"Failed to fetch markets: {e}") from e

        return [self._parse_market(m) for m in data]

    def get_market(self, condition_id: str) -> Market:
        """Fetch a single market by condition ID."""
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(f"{self._base_url}/markets/{condition_id}")
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as e:
            raise PolyClientError(f"Failed to fetch market {condition_id}: {e}") from e

        return self._parse_market(data)

    def get_positions(self, wallet_address: str) -> list[Position]:
        """Fetch open positions for a wallet address."""
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(
                    f"{self._base_url}/positions",
                    params={"user": wallet_address},
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as e:
            raise PolyClientError(f"Failed to fetch positions for {wallet_address}: {e}") from e

        return [
            Position(
                wallet_address=wallet_address,
                market_condition_id=p.get("condition_id", ""),
                side=p.get("side", "yes"),
                size=Decimal(str(p.get("size", 0))),
                avg_price=Decimal(str(p.get("avg_price", 0))),
                fetched_at=datetime.now(UTC),
            )
            for p in data
        ]

    def get_orderbook(self, token_id: str) -> dict[str, object]:
        """Fetch the orderbook for a specific token."""
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(
                    f"{self._base_url}/book",
                    params={"token_id": token_id},
                )
                response.raise_for_status()
                result: dict[str, object] = response.json()
                return result
        except httpx.HTTPError as e:
            raise PolyClientError(f"Failed to fetch orderbook for {token_id}: {e}") from e

    def _parse_market(self, data: dict[str, object]) -> Market:
        tokens_raw = data.get("tokens", [])
        token_yes: str | None = None
        token_no: str | None = None
        if isinstance(tokens_raw, list):
            for t in tokens_raw:
                if isinstance(t, dict):
                    outcome = str(t.get("outcome", "")).upper()
                    if outcome == "YES":
                        token_yes = t.get("token_id")
                    elif outcome == "NO":
                        token_no = t.get("token_id")

        return Market(
            condition_id=str(data.get("condition_id", "")),
            question=str(data.get("question", "")),
            token_id_yes=token_yes,
            token_id_no=token_no,
            active=bool(data.get("active", True)),
            fetched_at=datetime.now(UTC),
        )
