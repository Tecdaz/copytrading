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

    def __init__(
        self,
        positions_by_wallet: dict[str, list[Position]],
        midpoint: Decimal = Decimal("0.50"),
    ) -> None:
        self._positions = positions_by_wallet
        self._midpoint = midpoint
        self.midpoint_calls: list[str] = []

    def get_positions(self, address: str) -> list[Position]:
        return self._positions.get(address, [])

    def get_midpoint(self, token_id: str) -> Decimal:
        self.midpoint_calls.append(token_id)
        return self._midpoint

    def get_market(self, condition_id: str) -> Market:
        from copytrading.poly_client import PolyClientError

        raise PolyClientError("get_market not implemented in FakePolyClient")


def _seed_wallet(store: Store, address: str = "0xabc") -> None:
    store.upsert_wallet(
        Wallet(
            address=address,
            rank=1,
            total_pnl=Decimal("100"),
            discovered_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
    )


def _seed_market(
    store: Store,
    condition_id: str = "0xmkt",
    token_id_yes: str = "",
    token_id_no: str = "",
) -> None:
    store.upsert_market(
        Market(
            condition_id=condition_id,
            question="Test market?",
            token_id_yes=token_id_yes,
            token_id_no=token_id_no,
            fetched_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
    )


def _make_pos(
    wallet: str,
    market: str,
    side: str = "yes",
    avg_price: Decimal = Decimal("0.50"),
    cur_price: Decimal = Decimal("0.50"),
    asset: str = "tok_asset_123",
    size: Decimal = Decimal("10"),
) -> Position:
    return Position(
        wallet_address=wallet,
        market_condition_id=market,
        side=side,
        size=size,
        avg_price=avg_price,
        current_price=cur_price,
        asset=asset,
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
                        _make_pos("0xabc", "0xmkt", side="yes", avg_price=Decimal("0.50")),
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
                    _make_pos(
                        "0xabc", market_id, avg_price=Decimal("0.50"), cur_price=Decimal("0.50")
                    ),
                )

            # API says: 0xabc keeps existing positions, 0xdef has a new position
            poly: PolyClient = FakePolyClient(  # type: ignore[assignment]
                {
                    "0xabc": existing_positions,
                    "0xdef": [
                        _make_pos("0xdef", "0xmkt1"),
                    ],
                }
            )

            new_trades, closed_trades = copy_positions(poly, store)

            # 19 trades * 0.50 = 9.50 exposure. New trade: 1 * 0.50 = 0.50. Total = 10.00 ≤ 20
            assert len(new_trades) == 1
            assert len(closed_trades) == 0

    def test_exposure_limit_blocks_trade_when_already_at_limit(self) -> None:
        """Verify that new trades are blocked when exposure is already at 10%."""
        with Store(":memory:") as store:
            _seed_wallet(store, "0xabc")
            _seed_wallet(store, "0xdef")
            _seed_market(store, "0xmkt1")

            # Fill up to exactly 20 with existing trades (entry_price=1.00, size=1 → 1.00 each)
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
                        entry_price=Decimal("1.00"),
                        status="open",
                        opened_at=datetime(2024, 1, 1, tzinfo=UTC),
                    )
                )
                existing_positions.append(
                    _make_pos(
                        "0xabc", market_id, avg_price=Decimal("1.00"), cur_price=Decimal("1.00")
                    ),
                )

            # API says: 0xdef has a new position, but we're already at limit
            poly: PolyClient = FakePolyClient(  # type: ignore[assignment]
                {
                    "0xabc": existing_positions,
                    "0xdef": [
                        _make_pos("0xdef", "0xmkt1"),
                    ],
                }
            )

            new_trades, closed_trades = copy_positions(poly, store)

            # 20 + 0.50 = 20.50 > 20 → rejected
            assert len(new_trades) == 0
            assert len(closed_trades) == 0


class TestPositionFreshness:
    def test_stale_position_is_skipped(self) -> None:
        with Store(":memory:") as store:
            _seed_wallet(store, "0xabc")
            _seed_market(store, "0xmkt1")

            poly: PolyClient = FakePolyClient(
                {
                    "0xabc": [
                        _make_pos(
                            "0xabc", "0xmkt1", avg_price=Decimal("1.00"), cur_price=Decimal("1.02")
                        ),
                    ],
                }
            )  # type: ignore[assignment]

            new_trades, _ = copy_positions(poly, store)

            # Position has >1% deviation → skipped
            assert len(new_trades) == 0

    def test_fresh_position_is_copied(self) -> None:
        with Store(":memory:") as store:
            _seed_wallet(store, "0xabc")
            _seed_market(store, "0xmkt1")

            poly: PolyClient = FakePolyClient(
                {
                    "0xabc": [
                        _make_pos(
                            "0xabc", "0xmkt1", avg_price=Decimal("1.00"), cur_price=Decimal("1.01")
                        ),
                    ],
                }
            )  # type: ignore[assignment]

            new_trades, _ = copy_positions(poly, store)

            # Position is at exactly 1% boundary → copied
            assert len(new_trades) == 1


class TestEntryPriceValidation:
    def test_midpoint_over_equity_cap_is_skipped(self) -> None:
        with Store(":memory:") as store:
            _seed_wallet(store, "0xabc")
            _seed_market(store, "0xmkt1")

            # Equity=200, cap is 200*0.005 = 1.00. Midpoint 1.01 exceeds.
            poly: PolyClient = FakePolyClient(
                {
                    "0xabc": [
                        _make_pos("0xabc", "0xmkt1"),
                    ],
                },
                midpoint=Decimal("1.01"),
            )  # type: ignore[assignment]

            new_trades, _ = copy_positions(poly, store)

            assert len(new_trades) == 0

    def test_midpoint_within_equity_cap_is_copied(self) -> None:
        with Store(":memory:") as store:
            _seed_wallet(store, "0xabc")
            _seed_market(store, "0xmkt1")

            # Equity=200, cap=1.00. Midpoint 1.00 is allowed.
            poly: PolyClient = FakePolyClient(
                {
                    "0xabc": [
                        _make_pos("0xabc", "0xmkt1"),
                    ],
                },
                midpoint=Decimal("1.00"),
            )  # type: ignore[assignment]

            new_trades, _ = copy_positions(poly, store)

            assert len(new_trades) == 1


class TestRealExitPrice:
    def test_uses_midpoint_as_exit_price_with_token_id_yes(self) -> None:
        with Store(":memory:") as store:
            _seed_wallet(store)
            _seed_market(store, "0xmkt", token_id_yes="tok_yes_123")
            _trade_id = store.insert_paper_trade(
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

            # Midpoint moved to 0.70 — profit
            poly: PolyClient = FakePolyClient({"0xabc": []}, midpoint=Decimal("0.70"))  # type: ignore[assignment]

            _, closed_trades = copy_positions(poly, store)

            assert len(closed_trades) == 1
            assert closed_trades[0].exit_price == Decimal("0.70")
            # pnl = (0.70 - 0.50) * 1.00 = 0.20
            assert closed_trades[0].pnl == Decimal("0.20")
            assert poly.midpoint_calls == ["tok_yes_123"]  # type: ignore[attr-defined]

    def test_uses_midpoint_as_exit_price_with_token_id_no(self) -> None:
        with Store(":memory:") as store:
            _seed_wallet(store)
            _seed_market(store, "0xmkt", token_id_no="tok_no_456")
            store.insert_paper_trade(
                PaperTrade(
                    copied_from_wallet="0xabc",
                    market_condition_id="0xmkt",
                    side="no",
                    size=Decimal("1.00"),
                    entry_price=Decimal("0.50"),
                    status="open",
                    opened_at=datetime(2024, 1, 1, tzinfo=UTC),
                )
            )

            # Midpoint dropped — loss
            poly: PolyClient = FakePolyClient({"0xabc": []}, midpoint=Decimal("0.30"))  # type: ignore[assignment]

            _, closed_trades = copy_positions(poly, store)

            assert len(closed_trades) == 1
            assert closed_trades[0].exit_price == Decimal("0.30")
            # pnl = (0.30 - 0.50) * 1.00 = -0.20
            assert closed_trades[0].pnl == Decimal("-0.20")
            assert poly.midpoint_calls == ["tok_no_456"]  # type: ignore[attr-defined]

    def test_falls_back_to_entry_when_market_has_no_token_id(self) -> None:
        with Store(":memory:") as store:
            _seed_wallet(store)
            _seed_market(store, "0xmkt")  # No token_ids
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

            poly: PolyClient = FakePolyClient(  # type: ignore[assignment]
                {"0xabc": []}, midpoint=Decimal("0.70")
            )

            _, closed_trades = copy_positions(poly, store)

            # Fallback: exit_price = entry_price, pnl = 0
            assert closed_trades[0].exit_price == Decimal("0.50")
            assert closed_trades[0].pnl == Decimal("0")
            # Midpoint should NOT have been called
            assert poly.midpoint_calls == []  # type: ignore[attr-defined]

    def test_falls_back_when_midpoint_api_fails(self) -> None:
        from copytrading.poly_client import PolyClientError

        class FailingPoly(FakePolyClient):
            def get_midpoint(self, token_id: str) -> Decimal:
                raise PolyClientError("network down")

        with Store(":memory:") as store:
            _seed_wallet(store)
            _seed_market(store, "0xmkt", token_id_yes="tok_yes")
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

            poly: PolyClient = FailingPoly({"0xabc": []})  # type: ignore[assignment]

            _, closed_trades = copy_positions(poly, store)

            # Fallback on error
            assert closed_trades[0].exit_price == Decimal("0.50")
            assert closed_trades[0].pnl == Decimal("0")

    def test_persists_real_pnl_to_db(self) -> None:
        with Store(":memory:") as store:
            _seed_wallet(store)
            _seed_market(store, "0xmkt", token_id_yes="tok_yes")
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

            poly: PolyClient = FakePolyClient(  # type: ignore[assignment]
                {"0xabc": []}, midpoint=Decimal("0.80")
            )
            copy_positions(poly, store)

            # Verify DB has the real values, not placeholder
            row = store.conn.execute(
                "SELECT exit_price, pnl, status FROM paper_trades WHERE id=?",
                (trade_id,),
            ).fetchone()
            assert Decimal(row[0]) == Decimal("0.80")  # exit_price
            assert Decimal(row[1]) == Decimal("0.30")  # pnl = (0.80 - 0.50) * 1.00
            assert row[2] == "closed"


class TestUpdateLivePositions:
    def test_writes_one_row_per_open_trade(self) -> None:
        from copytrading.cronjobs.position_copier import update_live_positions
        from copytrading.sheets_client import SheetsClient
        from tests.conftest import FakeSheetsService

        fake_service = FakeSheetsService()
        sheets = SheetsClient(fake_service, "sheet123")

        with Store(":memory:") as store:
            store.upsert_market(
                Market(
                    condition_id="0xmkt",
                    question="?",
                    token_id_yes="tok_yes",
                    fetched_at=datetime(2024, 1, 1, tzinfo=UTC),
                )
            )
            _seed_wallet(store)
            store.insert_paper_trade(
                PaperTrade(
                    copied_from_wallet="0xabc",
                    market_condition_id="0xmkt",
                    side="yes",
                    size=Decimal("1.00"),
                    entry_price=Decimal("0.50"),
                    status="open",
                    opened_at=datetime(2024, 1, 1, tzinfo=UTC),
                    wallet_avg_price=Decimal("0.48"),
                    asset_token_id="tok_yes",
                )
            )

            poly: PolyClient = FakePolyClient(  # type: ignore[assignment]
                {"0xabc": []}, midpoint=Decimal("0.70")
            )
            update_live_positions(poly, store, sheets)

        # Header + 1 data row
        assert len(fake_service.writes) == 1
        range_name, values = fake_service.writes[0]
        assert range_name == "positions!A1"
        assert len(values) == 2
        # Row columns: id, opened, wallet, market, side, size, entry, current,
        # pnl, updated_at, wallet_avg_price, asset_token_id
        assert values[1][0] == "1"  # trade id
        assert values[1][3] == "0xmkt"
        assert values[1][6] == "0.50"  # entry
        assert values[1][7] == "0.70"  # current
        # unrealized pnl = (0.70 - 0.50) * 1.00 = 0.20
        assert Decimal(values[1][8]) == Decimal("0.20")
        assert values[1][10] == "0.48"  # wallet_avg_price
        assert values[1][11] == "tok_yes"  # asset_token_id

    def test_clears_sheet_when_no_open_trades(self) -> None:
        from copytrading.cronjobs.position_copier import update_live_positions
        from copytrading.sheets_client import SheetsClient
        from tests.conftest import FakeSheetsService

        fake_service = FakeSheetsService()
        sheets = SheetsClient(fake_service, "sheet123")

        with Store(":memory:") as store:
            poly: PolyClient = FakePolyClient(  # type: ignore[assignment]
                {"0xabc": []}, midpoint=Decimal("0.50")
            )
            update_live_positions(poly, store, sheets)

        # Header only, no data
        _, values = fake_service.writes[0]
        assert len(values) == 1
        assert values[0][0] == "Trade ID"
