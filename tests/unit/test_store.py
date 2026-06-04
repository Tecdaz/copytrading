"""Tests for SQLite store."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from copytrading.models import AccountSnapshot, Market, PaperTrade, Wallet
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

    def test_prune_wallets_not_in_removes_old(self) -> None:
        with Store(":memory:") as store:
            for addr in ["0xaaa", "0xbbb", "0xccc"]:
                store.upsert_wallet(
                    Wallet(
                        address=addr,
                        rank=1,
                        total_pnl=Decimal("0"),
                        discovered_at=datetime(2024, 1, 1, tzinfo=UTC),
                    )
                )

            deleted = store.prune_wallets_not_in(["0xaaa", "0xbbb"])

            assert deleted == 1
            remaining = {w.address for w in store.get_all_wallets()}
            assert remaining == {"0xaaa", "0xbbb"}

    def test_prune_wallets_not_in_cascades_to_paper_trades(self) -> None:
        with Store(":memory:") as store:
            # Seed two wallets + a market
            store.upsert_market(
                Market(
                    condition_id="cond1",
                    question="?",
                    fetched_at=datetime(2024, 1, 1, tzinfo=UTC),
                )
            )
            for addr in ["0xkeep", "0xdrop"]:
                store.upsert_wallet(
                    Wallet(
                        address=addr,
                        rank=1,
                        total_pnl=Decimal("0"),
                        discovered_at=datetime(2024, 1, 1, tzinfo=UTC),
                    )
                )
                # Use closed trades so the wallet can be pruned
                store.insert_paper_trade(
                    PaperTrade(
                        copied_from_wallet=addr,
                        market_condition_id="cond1",
                        side="yes",
                        size=Decimal("1.00"),
                        entry_price=Decimal("0.50"),
                        status="closed",
                        opened_at=datetime(2024, 1, 1, tzinfo=UTC),
                    )
                )

            store.prune_wallets_not_in(["0xkeep"])

            # The dropped wallet AND its paper_trades should be gone
            trades = store.conn.execute(
                "SELECT copied_from_wallet FROM paper_trades"
            ).fetchall()
            assert [t[0] for t in trades] == ["0xkeep"]

    def test_prune_with_empty_active_list_is_noop(self) -> None:
        with Store(":memory:") as store:
            store.upsert_wallet(
                Wallet(
                    address="0xaaa",
                    rank=1,
                    total_pnl=Decimal("0"),
                    discovered_at=datetime(2024, 1, 1, tzinfo=UTC),
                )
            )

            deleted = store.prune_wallets_not_in([])

            assert deleted == 0
            assert len(store.get_all_wallets()) == 1

    def test_prune_keeps_wallets_with_open_trades(self) -> None:
        with Store(":memory:") as store:
            store.upsert_market(
                Market(
                    condition_id="cond1",
                    question="?",
                    fetched_at=datetime(2024, 1, 1, tzinfo=UTC),
                )
            )
            # 0xkeep is in the new top 20
            store.upsert_wallet(
                Wallet(
                    address="0xkeep",
                    rank=1,
                    total_pnl=Decimal("0"),
                    discovered_at=datetime(2024, 1, 1, tzinfo=UTC),
                )
            )
            # 0xdangling dropped from top 20 but has an OPEN trade
            store.upsert_wallet(
                Wallet(
                    address="0xdangling",
                    rank=2,
                    total_pnl=Decimal("0"),
                    discovered_at=datetime(2024, 1, 1, tzinfo=UTC),
                )
            )
            store.insert_paper_trade(
                PaperTrade(
                    copied_from_wallet="0xdangling",
                    market_condition_id="cond1",
                    side="yes",
                    size=Decimal("1.00"),
                    entry_price=Decimal("0.50"),
                    status="open",
                    opened_at=datetime(2024, 1, 1, tzinfo=UTC),
                )
            )
            # 0xabandoned dropped from top 20 with no open trades
            store.upsert_wallet(
                Wallet(
                    address="0xabandoned",
                    rank=3,
                    total_pnl=Decimal("0"),
                    discovered_at=datetime(2024, 1, 1, tzinfo=UTC),
                )
            )

            deleted = store.prune_wallets_not_in(["0xkeep"])

            # Only the abandoned one is removed
            assert deleted == 1
            remaining = {w.address for w in store.get_all_wallets()}
            assert remaining == {"0xkeep", "0xdangling"}


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

    def test_get_all_paper_trades_caps_at_default_limit(self) -> None:
        with Store(":memory:") as store:
            self._seed_wallet(store)
            for i in range(600):
                store.insert_paper_trade(
                    PaperTrade(
                        copied_from_wallet="0xabc",
                        market_condition_id="cond1",
                        side="yes",
                        size=Decimal("1"),
                        entry_price=Decimal("0.50"),
                        opened_at=datetime(2024, 1, 1, i // 100, tzinfo=UTC),
                    )
                )

            trades = store.get_all_paper_trades()

            assert len(trades) == 500

    def test_get_all_paper_trades_orders_desc_by_opened_at(self) -> None:
        with Store(":memory:") as store:
            self._seed_wallet(store)
            for day in (1, 2, 3):
                store.insert_paper_trade(
                    PaperTrade(
                        copied_from_wallet="0xabc",
                        market_condition_id="cond1",
                        side="yes",
                        size=Decimal("1"),
                        entry_price=Decimal("0.50"),
                        opened_at=datetime(2024, 1, day, tzinfo=UTC),
                    )
                )

            trades = store.get_all_paper_trades(limit=500)

            opened_dates = [t.opened_at for t in trades if t.opened_at is not None]
            assert len(opened_dates) == 3
            assert opened_dates == sorted(opened_dates, reverse=True)
            assert opened_dates[0].day == 3
            assert opened_dates[-1].day == 1

    def test_get_all_paper_trades_honors_smaller_limit(self) -> None:
        with Store(":memory:") as store:
            self._seed_wallet(store)
            for i in range(5):
                store.insert_paper_trade(
                    PaperTrade(
                        copied_from_wallet="0xabc",
                        market_condition_id="cond1",
                        side="yes",
                        size=Decimal("1"),
                        entry_price=Decimal("0.50"),
                        opened_at=datetime(2024, 1, 1, i, tzinfo=UTC),
                    )
                )

            trades = store.get_all_paper_trades(limit=2)

            assert len(trades) == 2
            # The 2 most recent (highest hour) should come back
            assert trades[0].opened_at is not None
            assert trades[1].opened_at is not None
            assert trades[0].opened_at.hour > trades[1].opened_at.hour

    def test_get_all_paper_trades_empty_returns_empty_list(self) -> None:
        with Store(":memory:") as store:
            assert store.get_all_paper_trades(limit=500) == []

    def test_get_all_paper_trades_limit_at_sql_level(self) -> None:
        with Store(":memory:") as store:
            self._seed_wallet(store)
            for i in range(1000):
                store.insert_paper_trade(
                    PaperTrade(
                        copied_from_wallet="0xabc",
                        market_condition_id="cond1",
                        side="yes",
                        size=Decimal("1"),
                        entry_price=Decimal("0.50"),
                        opened_at=datetime(2024, 1, 1, i // 60, i % 60, tzinfo=UTC),
                    )
                )

            captured: list[str] = []
            store.conn.set_trace_callback(lambda sql: captured.append(sql))

            trades = store.get_all_paper_trades(limit=10)

            assert len(trades) == 10
            # At least one executed statement against paper_trades must contain "LIMIT 10"
            assert any("paper_trades" in sql and "LIMIT 10" in sql for sql in captured), (
                f"Expected SQL with 'LIMIT 10' against paper_trades, got: {captured}"
            )


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

    def test_get_all_snapshots_returns_ascending_order(self) -> None:
        with Store(":memory:") as store:
            # Insert in non-chronological order to prove the SQL does the sorting
            store.insert_account_snapshot(
                AccountSnapshot(
                    equity=Decimal("300"),
                    open_trades=2,
                    total_pnl=Decimal("100"),
                    snapshot_at=datetime(2024, 1, 3, tzinfo=UTC),
                )
            )
            store.insert_account_snapshot(
                AccountSnapshot(
                    equity=Decimal("100"),
                    open_trades=0,
                    total_pnl=Decimal("0"),
                    snapshot_at=datetime(2024, 1, 1, tzinfo=UTC),
                )
            )
            store.insert_account_snapshot(
                AccountSnapshot(
                    equity=Decimal("200"),
                    open_trades=1,
                    total_pnl=Decimal("50"),
                    snapshot_at=datetime(2024, 1, 2, tzinfo=UTC),
                )
            )

            snapshots = store.get_all_snapshots()

            assert len(snapshots) == 3
            snapshot_times = [s.snapshot_at for s in snapshots if s.snapshot_at is not None]
            assert len(snapshot_times) == 3
            assert snapshot_times[0] < snapshot_times[1] < snapshot_times[2]
            assert snapshots[0].equity == Decimal("100")
            assert snapshots[1].equity == Decimal("200")
            assert snapshots[2].equity == Decimal("300")

    def test_get_all_snapshots_empty_returns_empty_list(self) -> None:
        with Store(":memory:") as store:
            result = store.get_all_snapshots()

            assert result == []

    def test_get_all_snapshots_decimal_round_trip(self) -> None:
        with Store(":memory:") as store:
            store.insert_account_snapshot(
                AccountSnapshot(
                    equity=Decimal("200.50"),
                    open_trades=3,
                    total_pnl=Decimal("12.34"),
                    snapshot_at=datetime(2024, 1, 1, tzinfo=UTC),
                )
            )

            snapshots = store.get_all_snapshots()

            assert len(snapshots) == 1
            assert snapshots[0].equity == Decimal("200.50")
            assert snapshots[0].total_pnl == Decimal("12.34")
            assert snapshots[0].open_trades == 3
