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

    def test_exposure_limit_prevents_new_trades_when_at_10_percent(self) -> None:
        """Verify that new trades are blocked when exposure reaches 10% of equity."""
        with Store(":memory:") as store:
            _seed_wallet(store, "0xabc")
            _seed_wallet(store, "0xdef")
            _seed_market(store, "0xmkt1")
            _seed_market(store, "0xmkt2")

            # Equity is 200, so max exposure is 20 (10%)
            # Fill up to 19 with existing trades
            existing_positions = []
            for i in range(19):
                market_id = f"0xexisting{i}"
                _seed_market(store, market_id)
                store.insert_paper_trade(
                    PaperTrade(
                        copied_from_wallet="0xabc",
                        market_condition_id=market_id,
                        side="yes",
                        size=Decimal("1.00"),
                        entry_price=Decimal("0.50"),
                        status="open",
                        opened_at=datetime(2024, 1, 1, tzinfo=UTC),
                    )
                )
                # Add to fake API so they stay open
                existing_positions.append(
                    Position(
                        wallet_address="0xabc",
                        market_condition_id=market_id,
                        side="yes",
                        size=Decimal("10"),
                        avg_price=Decimal("0.50"),
                    )
                )

            # API says: 0xabc keeps existing positions, 0xdef has a new position
            poly: PolyClient = FakePolyClient(  # type: ignore[assignment]
                {
                    "0xabc": existing_positions,
                    "0xdef": [
                        Position(
                            wallet_address="0xdef",
                            market_condition_id="0xmkt1",
                            side="yes",
                            size=Decimal("10"),
                            avg_price=Decimal("0.50"),
                        )
                    ],
                }
            )

            new_trades, closed_trades = copy_positions(poly, store)

            # 19 + 1 = 20, which is exactly at limit (10% of 200)
            # This one should pass
            assert len(new_trades) == 1
            assert len(closed_trades) == 0

    def test_exposure_limit_blocks_trade_when_already_at_limit(self) -> None:
        """Verify that new trades are blocked when exposure is already at 10%."""
        with Store(":memory:") as store:
            _seed_wallet(store, "0xabc")
            _seed_wallet(store, "0xdef")
            _seed_market(store, "0xmkt1")

            # Equity is 200, so max exposure is 20 (10%)
            # Fill up to exactly 20 with existing trades
            existing_positions = []
            for i in range(20):
                market_id = f"0xexisting{i}"
                _seed_market(store, market_id)
                store.insert_paper_trade(
                    PaperTrade(
                        copied_from_wallet="0xabc",
                        market_condition_id=market_id,
                        side="yes",
                        size=Decimal("1.00"),
                        entry_price=Decimal("0.50"),
                        status="open",
                        opened_at=datetime(2024, 1, 1, tzinfo=UTC),
                    )
                )
                existing_positions.append(
                    Position(
                        wallet_address="0xabc",
                        market_condition_id=market_id,
                        side="yes",
                        size=Decimal("10"),
                        avg_price=Decimal("0.50"),
                    )
                )

            # API says: 0xdef has a new position, but we're already at limit
            poly: PolyClient = FakePolyClient(  # type: ignore[assignment]
                {
                    "0xabc": existing_positions,
                    "0xdef": [
                        Position(
                            wallet_address="0xdef",
                            market_condition_id="0xmkt1",
                            side="yes",
                            size=Decimal("10"),
                            avg_price=Decimal("0.50"),
                        )
                    ],
                }
            )

            new_trades, closed_trades = copy_positions(poly, store)

            # Should be rejected because we're already at 20 (10% limit)
            assert len(new_trades) == 0
            assert len(closed_trades) == 0
