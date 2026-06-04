"""Tests for domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from copytrading.models import (
    AccountSnapshot,
    Market,
    PaperTrade,
    Position,
    Wallet,
)


class TestWallet:
    def test_create_wallet(self) -> None:
        w = Wallet(
            address="0xabc",
            rank=1,
            total_pnl=Decimal("150.50"),
            discovered_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        assert w.address == "0xabc"
        assert w.rank == 1
        assert w.total_pnl == Decimal("150.50")
        assert w.last_checked_at is None

    def test_new_fields_have_defaults(self) -> None:
        w = Wallet(
            address="0xabc",
            rank=1,
            total_pnl=Decimal("0"),
            discovered_at=datetime.now(UTC),
        )
        assert w.username == ""
        assert w.x_username == ""
        assert w.volume == Decimal("0")
        assert w.verified_badge is False
        assert w.profile_image == ""

    def test_wallet_is_frozen(self) -> None:
        w = Wallet(
            address="0xabc",
            rank=1,
            total_pnl=Decimal("0"),
            discovered_at=datetime.now(UTC),
        )
        try:
            w.rank = 2  # type: ignore[misc]
            raise AssertionError("Wallet should be frozen")
        except AttributeError:
            pass


class TestMarket:
    def test_create_market(self) -> None:
        m = Market(
            condition_id="cond123",
            question="Will X happen?",
            token_id_yes="tok_yes",
            token_id_no="tok_no",
        )
        assert m.condition_id == "cond123"
        assert m.active is True


class TestPosition:
    def test_create_position(self) -> None:
        p = Position(
            wallet_address="0xabc",
            market_condition_id="cond123",
            side="yes",
            size=Decimal("100"),
            avg_price=Decimal("0.55"),
        )
        assert p.side == "yes"
        assert p.size == Decimal("100")


class TestPaperTrade:
    def test_create_open_trade(self) -> None:
        t = PaperTrade(
            copied_from_wallet="0xabc",
            market_condition_id="cond123",
            side="yes",
            size=Decimal("10"),
            entry_price=Decimal("0.50"),
            opened_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        assert t.status == "open"
        assert t.pnl == Decimal("0")
        assert t.exit_price is None

    def test_create_closed_trade_with_pnl(self) -> None:
        t = PaperTrade(
            copied_from_wallet="0xabc",
            market_condition_id="cond123",
            side="yes",
            size=Decimal("10"),
            entry_price=Decimal("0.50"),
            exit_price=Decimal("0.60"),
            status="closed",
            pnl=Decimal("1.00"),
            opened_at=datetime(2024, 1, 1, tzinfo=UTC),
            closed_at=datetime(2024, 1, 2, tzinfo=UTC),
        )
        assert t.status == "closed"
        assert t.pnl == Decimal("1.00")


class TestAccountSnapshot:
    def test_create_snapshot(self) -> None:
        s = AccountSnapshot(
            equity=Decimal("200"),
            open_trades=3,
            total_pnl=Decimal("5.50"),
            snapshot_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        assert s.equity == Decimal("200")
        assert s.open_trades == 3
