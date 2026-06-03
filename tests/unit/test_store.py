"""Tests for SQLite store."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from copytrading.models import AccountSnapshot, PaperTrade, Wallet
from copytrading.store import Store


class TestStoreLifecycle:
    def test_context_manager(self) -> None:
        with Store(":memory:") as store:
            assert store.conn is not None

    def test_schema_created(self) -> None:
        with Store(":memory:") as store:
            tables = store.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            names = [t[0] for t in tables]
            assert "wallets" in names
            assert "markets" in names
            assert "positions" in names
            assert "paper_trades" in names
            assert "account_snapshots" in names

    def test_wal_mode(self, tmp_path: Path) -> None:
        # WAL mode only applies to file-based databases, not :memory:
        db_file = tmp_path / "test.db"
        with Store(db_file) as store:
            mode = store.conn.execute("PRAGMA journal_mode").fetchone()
            assert mode[0] == "wal"


class TestWalletRepo:
    def test_upsert_and_get(self) -> None:
        with Store(":memory:") as store:
            w = Wallet(
                address="0xabc",
                rank=1,
                total_pnl=Decimal("100.50"),
                discovered_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
            store.upsert_wallet(w)

            wallets = store.get_all_wallets()
            assert len(wallets) == 1
            assert wallets[0].address == "0xabc"
            assert wallets[0].total_pnl == Decimal("100.50")

    def test_upsert_updates_existing(self) -> None:
        with Store(":memory:") as store:
            w1 = Wallet(
                address="0xabc",
                rank=1,
                total_pnl=Decimal("100"),
                discovered_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
            store.upsert_wallet(w1)

            w2 = Wallet(
                address="0xabc",
                rank=2,
                total_pnl=Decimal("200"),
                discovered_at=datetime(2024, 1, 1, tzinfo=UTC),
                last_checked_at=datetime(2024, 1, 2, tzinfo=UTC),
            )
            store.upsert_wallet(w2)

            wallets = store.get_all_wallets()
            assert len(wallets) == 1
            assert wallets[0].rank == 2
            assert wallets[0].total_pnl == Decimal("200")

    def test_get_all_ordered_by_rank(self) -> None:
        with Store(":memory:") as store:
            for i in [3, 1, 2]:
                store.upsert_wallet(
                    Wallet(
                        address=f"0x{i}",
                        rank=i,
                        total_pnl=Decimal("0"),
                        discovered_at=datetime(2024, 1, 1, tzinfo=UTC),
                    )
                )

            wallets = store.get_all_wallets()
            assert [w.rank for w in wallets] == [1, 2, 3]


class TestPaperTradeRepo:
    def _seed_wallet(self, store: Store) -> None:
        store.upsert_wallet(
            Wallet(
                address="0xabc",
                rank=1,
                total_pnl=Decimal("0"),
                discovered_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )
        store.conn.execute(
            "INSERT INTO markets (condition_id, question, fetched_at) VALUES (?, ?, ?)",
            ("cond1", "Test?", datetime.now(UTC).isoformat()),
        )
        store.conn.commit()

    def test_insert_and_get_open(self) -> None:
        with Store(":memory:") as store:
            self._seed_wallet(store)

            trade = PaperTrade(
                copied_from_wallet="0xabc",
                market_condition_id="cond1",
                side="yes",
                size=Decimal("10"),
                entry_price=Decimal("0.50"),
                opened_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
            trade_id = store.insert_paper_trade(trade)
            assert trade_id > 0

            open_trades = store.get_open_paper_trades()
            assert len(open_trades) == 1
            assert open_trades[0].status == "open"

    def test_close_trade(self) -> None:
        with Store(":memory:") as store:
            self._seed_wallet(store)

            trade = PaperTrade(
                copied_from_wallet="0xabc",
                market_condition_id="cond1",
                side="yes",
                size=Decimal("10"),
                entry_price=Decimal("0.50"),
                opened_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
            trade_id = store.insert_paper_trade(trade)

            store.update_paper_trade_status(
                trade_id, "closed", exit_price=Decimal("0.60"), pnl=Decimal("1.00")
            )

            open_trades = store.get_open_paper_trades()
            assert len(open_trades) == 0


class TestAccountSnapshotRepo:
    def test_insert_and_get_latest(self) -> None:
        with Store(":memory:") as store:
            snap = AccountSnapshot(
                equity=Decimal("200"),
                open_trades=0,
                total_pnl=Decimal("0"),
                snapshot_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
            store.insert_account_snapshot(snap)

            latest = store.get_latest_snapshot()
            assert latest is not None
            assert latest.equity == Decimal("200")

    def test_get_latest_returns_most_recent(self) -> None:
        with Store(":memory:") as store:
            store.insert_account_snapshot(
                AccountSnapshot(
                    equity=Decimal("200"),
                    open_trades=0,
                    snapshot_at=datetime(2024, 1, 1, tzinfo=UTC),
                )
            )
            store.insert_account_snapshot(
                AccountSnapshot(
                    equity=Decimal("205"),
                    open_trades=1,
                    total_pnl=Decimal("5"),
                    snapshot_at=datetime(2024, 1, 2, tzinfo=UTC),
                )
            )

            latest = store.get_latest_snapshot()
            assert latest is not None
            assert latest.equity == Decimal("205")

    def test_get_latest_empty(self) -> None:
        with Store(":memory:") as store:
            assert store.get_latest_snapshot() is None
