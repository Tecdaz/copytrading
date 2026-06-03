"""Tests for Polymarket public API client."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import httpx
import pytest

from copytrading.poly_client import PolyClient, PolyClientError
from tests.conftest import FakeHTTPClient


class TestPolyClientReadOnly:
    def test_no_write_methods(self) -> None:
        """PolyClient must not have any write/execute methods."""
        client = PolyClient()
        forbidden = ["place", "cancel", "create_order", "post_order", "execute"]
        for name in dir(client):
            if name.startswith("_"):
                continue
            for word in forbidden:
                assert word not in name.lower(), f"Found forbidden method: {name}"

    def test_no_py_clob_client_import(self) -> None:
        """Module must not import py_clob_client."""
        import sys

        import copytrading.poly_client  # noqa: F401

        assert "py_clob_client" not in sys.modules


class TestPolyClientGetMarkets:
    def test_parse_markets(self) -> None:
        fake = FakeHTTPClient(
            responses={
                "https://clob.polymarket.com/markets": [
                    {
                        "condition_id": "cond1",
                        "question": "Will X happen?",
                        "tokens": [
                            {"outcome": "YES", "token_id": "tok_yes"},
                            {"outcome": "NO", "token_id": "tok_no"},
                        ],
                        "active": True,
                    }
                ]
            }
        )

        with patch("copytrading.poly_client.httpx.Client", return_value=fake):
            client = PolyClient()
            markets = client.get_markets()

        assert len(markets) == 1
        assert markets[0].condition_id == "cond1"
        assert markets[0].token_id_yes == "tok_yes"
        assert markets[0].token_id_no == "tok_no"

    def test_http_error_raises_poly_error(self) -> None:
        fake = FakeHTTPClient(
            responses={
                "https://clob.polymarket.com/markets": httpx.HTTPStatusError(
                    "Server error",
                    request=httpx.Request("GET", "http://test"),
                    response=httpx.Response(500),
                )
            }
        )

        with patch("copytrading.poly_client.httpx.Client", return_value=fake):
            client = PolyClient()
            with pytest.raises(PolyClientError):
                client.get_markets()


class TestPolyClientGetPositions:
    def test_parse_positions(self) -> None:
        fake = FakeHTTPClient(
            responses={
                "https://data-api.polymarket.com/positions": [
                    {
                        "conditionId": "cond1",
                        "outcome": "Alexander Zverev",
                        "outcomeIndex": 1,
                        "size": 100,
                        "avgPrice": 0.55,
                        "curPrice": 0.60,
                        "initialValue": 55,
                        "currentValue": 60,
                        "cashPnl": 5,
                        "title": "Test Market",
                    }
                ]
            }
        )

        with patch("copytrading.poly_client.httpx.Client", return_value=fake):
            client = PolyClient()
            positions = client.get_positions("0xabc")

        assert len(positions) == 1
        assert positions[0].wallet_address == "0xabc"
        assert positions[0].side == "Alexander Zverev"
        assert positions[0].outcome_index == 1
        assert positions[0].size == Decimal("100")
        assert positions[0].avg_price == Decimal("0.55")
        assert positions[0].current_price == Decimal("0.60")
        assert positions[0].initial_value == Decimal("55")
        assert positions[0].current_value == Decimal("60")
        assert positions[0].cash_pnl == Decimal("5")
        assert positions[0].title == "Test Market"


class TestPolyClientGetOrderbook:
    def test_fetch_orderbook(self) -> None:
        fake = FakeHTTPClient(
            responses={
                "https://clob.polymarket.com/book": {
                    "bids": [{"price": "0.50", "size": "100"}],
                    "asks": [{"price": "0.55", "size": "50"}],
                }
            }
        )

        with patch("copytrading.poly_client.httpx.Client", return_value=fake):
            client = PolyClient()
            book = client.get_orderbook("tok123")

        assert "bids" in book
        assert "asks" in book
