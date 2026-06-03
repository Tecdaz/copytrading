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
                result = response.json()
                # API returns {"data": [...], "next_cursor": ..., "limit": ..., "count": ...}
                markets_data = result.get("data", []) if isinstance(result, dict) else result
        except httpx.HTTPError as e:
            raise PolyClientError(f"Failed to fetch markets: {e}") from e

        return [self._parse_market(m) for m in markets_data]

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
        """Fetch open positions for a wallet address from data-api."""
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(
                    "https://data-api.polymarket.com/positions",
                    params={"user": wallet_address},
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as e:
            raise PolyClientError(f"Failed to fetch positions for {wallet_address}: {e}") from e

        return [
            Position(
                wallet_address=wallet_address,
                market_condition_id=p.get("conditionId", ""),
                side=p.get("outcome", ""),
                outcome_index=p.get("outcomeIndex", 0),
                size=Decimal(str(p.get("size", 0))),
                avg_price=Decimal(str(p.get("avgPrice", 0))),
                current_price=Decimal(str(p.get("curPrice", 0))),
                initial_value=Decimal(str(p.get("initialValue", 0))),
                current_value=Decimal(str(p.get("currentValue", 0))),
                cash_pnl=Decimal(str(p.get("cashPnl", 0))),
                title=p.get("title", ""),
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
        token_first: str | None = None
        token_second: str | None = None

        if isinstance(tokens_raw, list) and len(tokens_raw) >= 2:
            # Polymarket uses outcome names (not YES/NO), so we take first two tokens
            if isinstance(tokens_raw[0], dict):
                token_first = tokens_raw[0].get("token_id")
            if isinstance(tokens_raw[1], dict):
                token_second = tokens_raw[1].get("token_id")

        return Market(
            condition_id=str(data.get("condition_id", "")),
            question=str(data.get("question", "")),
            token_id_yes=token_first,
            token_id_no=token_second,
            active=bool(data.get("active", True)),
            fetched_at=datetime.now(UTC),
        )
