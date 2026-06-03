"""Tests for leaderboard discovery logic."""

from __future__ import annotations

from unittest.mock import patch

from copytrading.cronjobs.leaderboard_discovery import fetch_top_traders
from copytrading.poly_client import PolyClient
from tests.conftest import FakeHTTPClient


class FakePoly:
    """Minimal PolyClient stub for fetch_top_traders tests."""

    def __init__(self, raw_entries: list[dict]) -> None:
        self._raw = raw_entries
        self.calls: list[dict] = []

    def get_leaderboard(
        self,
        time_period: str = "DAY",
        limit: int = 50,
        order_by: str = "VOL",
    ) -> list[dict]:
        self.calls.append(
            {"time_period": time_period, "limit": limit, "order_by": order_by}
        )
        return self._raw


class TestFetchTopTraders:
    def test_filters_out_negative_pnl(self) -> None:
        raw = [
            {"proxyWallet": "0xaaa", "userName": "winner1", "pnl": 500, "vol": 1000},
            {"proxyWallet": "0xbbb", "userName": "loser1", "pnl": -200, "vol": 5000},
            {"proxyWallet": "0xccc", "userName": "winner2", "pnl": 100, "vol": 2000},
        ]
        poly = FakePoly(raw)
        entries = fetch_top_traders(poly, limit=20)  # type: ignore[arg-type]

        usernames = [e.username for e in entries]
        assert "loser1" not in usernames
        assert "winner1" in usernames
        assert "winner2" in usernames

    def test_filters_out_zero_pnl(self) -> None:
        raw = [
            {"proxyWallet": "0xaaa", "userName": "breakeven", "pnl": 0, "vol": 3000},
            {"proxyWallet": "0xbbb", "userName": "winner", "pnl": 100, "vol": 1000},
        ]
        poly = FakePoly(raw)
        entries = fetch_top_traders(poly, limit=20)  # type: ignore[arg-type]

        assert len(entries) == 1
        assert entries[0].username == "winner"

    def test_sorted_by_volume_descending(self) -> None:
        raw = [
            {"proxyWallet": "0xaaa", "userName": "low_vol", "pnl": 100, "vol": 100},
            {"proxyWallet": "0xbbb", "userName": "high_vol", "pnl": 100, "vol": 10000},
            {"proxyWallet": "0xccc", "userName": "mid_vol", "pnl": 100, "vol": 1000},
        ]
        poly = FakePoly(raw)
        entries = fetch_top_traders(poly, limit=20)  # type: ignore[arg-type]

        assert [e.username for e in entries] == ["high_vol", "mid_vol", "low_vol"]

    def test_ranks_are_sequential_after_filtering(self) -> None:
        raw = [
            {"proxyWallet": "0xaaa", "userName": "loser", "pnl": -500, "vol": 99999},
            {"proxyWallet": "0xbbb", "userName": "winner1", "pnl": 100, "vol": 5000},
            {"proxyWallet": "0xccc", "userName": "winner2", "pnl": 200, "vol": 3000},
        ]
        poly = FakePoly(raw)
        entries = fetch_top_traders(poly, limit=20)  # type: ignore[arg-type]

        assert [e.rank for e in entries] == [1, 2]

    def test_limit_caps_results(self) -> None:
        raw = [
            {"proxyWallet": f"0x{i:040x}", "userName": f"t{i}", "pnl": 100, "vol": 1000 - i}
            for i in range(30)
        ]
        poly = FakePoly(raw)
        entries = fetch_top_traders(poly, limit=20)  # type: ignore[arg-type]

        assert len(entries) == 20
        assert entries[0].rank == 1
        assert entries[19].rank == 20

    def test_requests_50_with_order_by_volume(self) -> None:
        poly = FakePoly([])
        fetch_top_traders(poly, limit=20)  # type: ignore[arg-type]

        assert len(poly.calls) == 1
        call = poly.calls[0]
        assert call["time_period"] == "DAY"
        assert call["order_by"] == "VOL"
        assert call["limit"] == 50  # Fetch max from API to have headroom for filtering

    def test_empty_response_returns_empty_list(self) -> None:
        poly = FakePoly([])
        entries = fetch_top_traders(poly, limit=20)  # type: ignore[arg-type]
        assert entries == []

    def test_all_negative_pnl_returns_empty(self) -> None:
        raw = [
            {"proxyWallet": "0xaaa", "userName": "loser1", "pnl": -100, "vol": 1000},
            {"proxyWallet": "0xbbb", "userName": "loser2", "pnl": -200, "vol": 2000},
        ]
        poly = FakePoly(raw)
        entries = fetch_top_traders(poly, limit=20)  # type: ignore[arg-type]
        assert entries == []
