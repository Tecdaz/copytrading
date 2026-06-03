"""Tests for Google Sheets client."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from copytrading.models import AccountSnapshot, PaperTrade, Wallet
from copytrading.sheets_client import SheetsClient
from tests.conftest import FakeSheetsService


class TestSheetsClientUpdateLeaderboard:
    def test_writes_wallet_data(self) -> None:
        fake_service = FakeSheetsService()
        client = SheetsClient(fake_service, "sheet123")

        wallets = [
            Wallet(
                address="0xabc",
                rank=1,
                total_pnl=Decimal("100.50"),
                discovered_at=datetime(2024, 1, 1, tzinfo=UTC),
                last_checked_at=datetime(2024, 1, 2, tzinfo=UTC),
            ),
            Wallet(
                address="0xdef",
                rank=2,
                total_pnl=Decimal("-50.25"),
                discovered_at=datetime(2024, 1, 1, tzinfo=UTC),
            ),
        ]

        client.update_leaderboard(wallets)

        assert len(fake_service.writes) == 1
        range_name, values = fake_service.writes[0]
        assert range_name == "leaderboard!A1"
        assert len(values) == 3  # header + 2 wallets
        assert values[0] == ["Rank", "Address", "Total PnL", "Last Checked", "Profile Link"]
        assert values[1][0] == "1"  # rank (as string)
        assert values[1][1] == "0xabc"  # address


class TestSheetsClientAppendTrades:
    def test_appends_trade_data(self) -> None:
        fake_service = FakeSheetsService()
        client = SheetsClient(fake_service, "sheet123")

        trades = [
            PaperTrade(
                copied_from_wallet="0xabc",
                market_condition_id="cond1",
                side="yes",
                size=Decimal("10"),
                entry_price=Decimal("0.50"),
                status="open",
                opened_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
        ]

        client.append_trades(trades)

        assert len(fake_service.appends) == 1
        range_name, values = fake_service.appends[0]
        assert "history" in range_name
        assert len(values) == 1
        assert values[0][1] == "0xabc"  # copied_from_wallet
        assert values[0][10] == ""  # no market_url set on this trade

    def test_appends_market_link_column(self) -> None:
        fake_service = FakeSheetsService()
        client = SheetsClient(fake_service, "sheet123")

        trades = [
            PaperTrade(
                copied_from_wallet="0xabc",
                market_condition_id="0xmarket123",
                side="yes",
                size=Decimal("10"),
                entry_price=Decimal("0.50"),
                status="open",
                opened_at=datetime(2024, 1, 1, tzinfo=UTC),
                market_url="https://polymarket.com/market/0xmarket123",
            )
        ]

        client.append_trades(trades)

        _, values = fake_service.appends[0]
        # Row should have 11 columns (10 + market link)
        assert len(values[0]) == 11
        assert values[0][10] == "https://polymarket.com/market/0xmarket123"

    def test_empty_market_url_writes_empty_string(self) -> None:
        fake_service = FakeSheetsService()
        client = SheetsClient(fake_service, "sheet123")

        trades = [
            PaperTrade(
                copied_from_wallet="0xabc",
                market_condition_id="cond1",
                side="yes",
                size=Decimal("10"),
                entry_price=Decimal("0.50"),
                status="open",
                opened_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
        ]

        client.append_trades(trades)

        _, values = fake_service.appends[0]
        assert values[0][10] == ""  # No market_url set

    def test_empty_trades_noop(self) -> None:
        fake_service = FakeSheetsService()
        client = SheetsClient(fake_service, "sheet123")

        client.append_trades([])

        assert len(fake_service.appends) == 0


class TestSheetsClientEnsureHistoryHeader:
    def test_writes_header_when_sheet_is_empty(self) -> None:
        fake_service = FakeSheetsService()
        client = SheetsClient(fake_service, "sheet123")

        client.ensure_history_header()

        assert len(fake_service.writes) == 1
        range_name, values = fake_service.writes[0]
        assert range_name == "history!A1"
        assert values == [
            [
                "Opened At",
                "Wallet",
                "Market",
                "Side",
                "Size",
                "Entry Price",
                "Exit Price",
                "Status",
                "PnL",
                "Closed At",
                "Market Link",
            ]
        ]

    def test_does_not_overwrite_existing_header(self) -> None:
        fake_service = FakeSheetsService()
        # Simulate existing header
        fake_service._storage["history!A1"] = [
            [
                "Old Header",
                "x",
                "x",
                "x",
                "x",
                "x",
                "x",
                "x",
                "x",
                "x",
            ]
        ]
        client = SheetsClient(fake_service, "sheet123")

        client.ensure_history_header()

        assert len(fake_service.writes) == 0


class TestSheetsClientUpdateAccount:
    def test_writes_account_snapshot(self) -> None:
        fake_service = FakeSheetsService()
        client = SheetsClient(fake_service, "sheet123")

        snapshot = AccountSnapshot(
            equity=Decimal("205.50"),
            open_trades=2,
            total_pnl=Decimal("5.50"),
            snapshot_at=datetime(2024, 1, 1, tzinfo=UTC),
        )

        client.update_account(snapshot)

        assert len(fake_service.writes) == 1
        range_name, values = fake_service.writes[0]
        assert range_name == "account!A1"
        assert values[0] == ["Timestamp", "Equity", "Open Trades", "Total PnL"]
        assert values[1][1] == "205.50"  # equity
