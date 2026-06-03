"""Tests for the position_copier cronjob logic."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from copytrading.cronjobs.position_copier import copy_positions
from copytrading.models import Market, PaperTrade, Position, Wallet
from copytrading.poly_client import PolyClient
from copytrading.store import Store


class FakePolyClient:
    """Fake PolyClient that returns pre-canned positions per wallet."""

    def __init__(self, positions_by_wallet: dict[str, list[Position]]) -> None:
        self._positions = positions_by_wallet

    def get_positions(self, address: str) -> list[Position]:
        return self._positions.get(address, [])


def _seed_wallet(store: Store, address: str = "0xabc") -> None:
    store.upsert_wallet(
        Wallet(
            address=address,
            rank=1,
            total_pnl=Decimal("100"),
            discovered_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
    )


def _seed_market(store: Store, condition_id: str = "0xmkt") -> None:
    store.upsert_market(
        Market(
            condition_id=condition_id,
            question="Test market?",
            fetched_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
    )


class TestCopyPositions:
    def test_open_trade_becomes_closed_when_position_disappears(self) -> None:
        with Store(":memory:") as store:
            _seed_wallet(store)
            _seed_market(store)
            trade_id = store.insert_paper_trade(
                PaperTrade(
                    copied_from_wallet="0xabc",
                    market_condition_id="0xmkt",
                    side="yes",
                    size=Decimal("1.00"),
                    entry_price=Decimal("0.50"),
                    status="open",
                    opened_at=datetime(2024, 1, 1, tzinfo=UTC),
                )
            )
            assert trade_id is not None

            # API says: wallet has no positions anymore
            poly: PolyClient = FakePolyClient({"0xabc": []})  # type: ignore[assignment]

            new_trades, closed_trades = copy_positions(poly, store)

            assert len(new_trades) == 0
            assert len(closed_trades) == 1
            assert closed_trades[0].id == trade_id
            assert closed_trades[0].status == "closed"
            assert closed_trades[0].exit_price == Decimal("0.50")  # placeholder
            assert closed_trades[0].closed_at is not None

    def test_open_trade_stays_open_when_position_still_present(self) -> None:
        with Store(":memory:") as store:
            _seed_wallet(store)
            _seed_market(store)
            store.insert_paper_trade(
                PaperTrade(
                    copied_from_wallet="0xabc",
                    market_condition_id="0xmkt",
                    side="yes",
                    size=Decimal("1.00"),
                    entry_price=Decimal("0.50"),
                    status="open",
                    opened_at=datetime(2024, 1, 1, tzinfo=UTC),
                )
            )
            poly: PolyClient = FakePolyClient(
                {
                    "0xabc": [
                        Position(
                            wallet_address="0xabc",
                            market_condition_id="0xmkt",
                            side="yes",
                            size=Decimal("10"),
                            avg_price=Decimal("0.50"),
                        )
                    ]
                }
            )  # type: ignore[assignment]

            new_trades, closed_trades = copy_positions(poly, store)

            assert len(new_trades) == 0
            assert len(closed_trades) == 0
