"""SQLite storage with repository pattern."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Self

from copytrading.models import (
    AccountSnapshot,
    Market,
    PaperTrade,
    Wallet,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS wallets (
    address TEXT PRIMARY KEY,
    rank INTEGER NOT NULL,
    total_pnl TEXT NOT NULL,
    discovered_at TEXT NOT NULL,
    last_checked_at TEXT,
    profile_url TEXT NOT NULL DEFAULT '',
    username TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS markets (
    condition_id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    token_id_yes TEXT,
    token_id_no TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_address TEXT NOT NULL REFERENCES wallets(address),
    market_condition_id TEXT NOT NULL REFERENCES markets(condition_id),
    side TEXT NOT NULL,
    size TEXT NOT NULL,
    avg_price TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    UNIQUE(wallet_address, market_condition_id, side)
);

CREATE TABLE IF NOT EXISTS paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    copied_from_wallet TEXT NOT NULL REFERENCES wallets(address),
    market_condition_id TEXT NOT NULL REFERENCES markets(condition_id),
    side TEXT NOT NULL,
    size TEXT NOT NULL,
    entry_price TEXT NOT NULL,
    exit_price TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'closed')),
    pnl TEXT NOT NULL DEFAULT '0',
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    market_url TEXT NOT NULL DEFAULT '',
    asset_token_id TEXT NOT NULL DEFAULT '',
    wallet_avg_price TEXT NOT NULL DEFAULT '0',
    wallet_cur_price TEXT NOT NULL DEFAULT '0',
    initial_value TEXT NOT NULL DEFAULT '0',
    current_value TEXT NOT NULL DEFAULT '0',
    total_bought TEXT NOT NULL DEFAULT '0',
    realized_pnl TEXT NOT NULL DEFAULT '0',
    percent_pnl TEXT NOT NULL DEFAULT '0',
    percent_realized_pnl TEXT NOT NULL DEFAULT '0',
    redeemable INTEGER NOT NULL DEFAULT 0,
    mergeable INTEGER NOT NULL DEFAULT 0,
    market_title TEXT NOT NULL DEFAULT '',
    market_slug TEXT NOT NULL DEFAULT '',
    market_icon TEXT NOT NULL DEFAULT '',
    event_id TEXT NOT NULL DEFAULT '',
    event_slug TEXT NOT NULL DEFAULT '',
    end_date TEXT NOT NULL DEFAULT '',
    negative_risk INTEGER NOT NULL DEFAULT 0,
    opposite_outcome TEXT NOT NULL DEFAULT '',
    opposite_asset TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS account_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equity TEXT NOT NULL,
    open_trades INTEGER NOT NULL,
    total_pnl TEXT NOT NULL DEFAULT '0',
    snapshot_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_paper_trades_status ON paper_trades(status);
CREATE INDEX IF NOT EXISTS idx_paper_trades_wallet ON paper_trades(copied_from_wallet);
CREATE INDEX IF NOT EXISTS idx_positions_wallet ON positions(wallet_address);
"""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class Store:
    """SQLite store with WAL mode and context manager support."""

    def __init__(self, db_path: str | Path = "copytrading.db") -> None:
        self._db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> Self:
        # check_same_thread=False is required for FastAPI's async dependency
        # injection: the generator opens the connection in a threadpool thread
        # but the cleanup (__exit__) runs in the main event-loop thread.
        # Safe for the read-only dashboard and for the single-threaded cronjobs.
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        return self

    def __exit__(self, *args: object) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Store must be used as a context manager")
        return self._conn

    # -- Wallet repository --

    def upsert_wallet(self, wallet: Wallet) -> None:
        self.conn.execute(
            """INSERT INTO wallets (
                   address, rank, total_pnl, discovered_at, last_checked_at, profile_url, username
               )
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(address) DO UPDATE SET
                   rank=excluded.rank,
                   total_pnl=excluded.total_pnl,
                   last_checked_at=excluded.last_checked_at,
                   profile_url=excluded.profile_url,
                   username=excluded.username""",
            (
                wallet.address,
                wallet.rank,
                str(wallet.total_pnl),
                wallet.discovered_at.isoformat(),
                wallet.last_checked_at.isoformat() if wallet.last_checked_at else None,
                wallet.profile_url,
                wallet.username,
            ),
        )
        self.conn.commit()

    def get_all_wallets(self) -> list[Wallet]:
        rows = self.conn.execute(
            "SELECT address, rank, total_pnl, discovered_at, last_checked_at, "
            "profile_url, username "
            "FROM wallets ORDER BY rank"
        ).fetchall()
        return [
            Wallet(
                address=r[0],
                rank=r[1],
                total_pnl=Decimal(r[2]),
                discovered_at=datetime.fromisoformat(r[3]),
                last_checked_at=datetime.fromisoformat(r[4]) if r[4] else None,
                profile_url=r[5] if r[5] else "",
                username=r[6] if r[6] else "",
            )
            for r in rows
        ]

    def prune_wallets_not_in(self, active_addresses: list[str]) -> int:
        """Delete wallets not in the active leaderboard that have no open trades.

        Wallets dropped from the top N are kept if they still have open paper
        trades — the position copier needs them to detect closures. Once all
        their trades close, the next prune will remove them.

        Closed paper_trades for pruned wallets are also deleted (history
        stays in Google Sheets).

        Args:
            active_addresses: Addresses that should remain in the table.

        Returns:
            Number of wallets deleted.
        """
        if not active_addresses:
            return 0

        normalized = [a.lower() for a in active_addresses]
        placeholders = ",".join("?" for _ in normalized)

        # Find wallets to prune: not in active list AND no open trades
        cursor = self.conn.execute(
            f"""
            SELECT address FROM wallets
            WHERE address NOT IN ({placeholders})
              AND address NOT IN (
                  SELECT DISTINCT copied_from_wallet
                  FROM paper_trades
                  WHERE status = 'open'
              )
            """,
            normalized,
        )
        to_remove = [row[0] for row in cursor.fetchall()]

        if not to_remove:
            return 0

        rm_placeholders = ",".join("?" for _ in to_remove)

        # Delete their (non-open) paper_trades
        self.conn.execute(
            f"DELETE FROM paper_trades WHERE copied_from_wallet IN ({rm_placeholders})",
            to_remove,
        )

        # Delete the wallets themselves
        cursor = self.conn.execute(
            f"DELETE FROM wallets WHERE address IN ({rm_placeholders})",
            to_remove,
        )
        self.conn.commit()
        return cursor.rowcount

    # -- Market repository --

    def upsert_market(self, market: Market) -> None:
        self.conn.execute(
            """INSERT INTO markets
               (condition_id, question, token_id_yes, token_id_no, active, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(condition_id) DO UPDATE SET
                   question=excluded.question,
                   token_id_yes=excluded.token_id_yes,
                   token_id_no=excluded.token_id_no,
                   active=excluded.active,
                   fetched_at=excluded.fetched_at""",
            (
                market.condition_id,
                market.question,
                market.token_id_yes,
                market.token_id_no,
                1 if market.active else 0,
                market.fetched_at.isoformat() if market.fetched_at else _now_iso(),
            ),
        )
        self.conn.commit()

    def get_market(self, condition_id: str) -> Market | None:
        row = self.conn.execute(
            """SELECT condition_id, question, token_id_yes, token_id_no, active, fetched_at
               FROM markets WHERE condition_id=?""",
            (condition_id,),
        ).fetchone()
        if row is None:
            return None
        return Market(
            condition_id=row[0],
            question=row[1],
            token_id_yes=row[2],
            token_id_no=row[3],
            active=bool(row[4]),
            fetched_at=datetime.fromisoformat(row[5]),
        )

    # -- Paper trade repository --

    def insert_paper_trade(self, trade: PaperTrade) -> int:
        cursor = self.conn.execute(
            """INSERT INTO paper_trades
               (copied_from_wallet, market_condition_id, side, size,
                entry_price, exit_price, status, pnl, opened_at, closed_at,
                market_url, asset_token_id, wallet_avg_price, wallet_cur_price,
                initial_value, current_value, total_bought, realized_pnl,
                percent_pnl, percent_realized_pnl, redeemable, mergeable,
                market_title, market_slug, market_icon, event_id, event_slug,
                end_date, negative_risk, opposite_outcome, opposite_asset)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?,
                       ?, ?, ?, ?,
                       ?, ?, ?, ?,
                       ?, ?, ?, ?, ?,
                       ?, ?, ?, ?)""",
            (
                trade.copied_from_wallet,
                trade.market_condition_id,
                trade.side,
                str(trade.size),
                str(trade.entry_price),
                str(trade.exit_price) if trade.exit_price is not None else None,
                trade.status,
                str(trade.pnl),
                trade.opened_at.isoformat() if trade.opened_at else _now_iso(),
                trade.closed_at.isoformat() if trade.closed_at else None,
                trade.market_url,
                trade.asset_token_id,
                str(trade.wallet_avg_price),
                str(trade.wallet_cur_price),
                str(trade.initial_value),
                str(trade.current_value),
                str(trade.total_bought),
                str(trade.realized_pnl),
                str(trade.percent_pnl),
                str(trade.percent_realized_pnl),
                1 if trade.redeemable else 0,
                1 if trade.mergeable else 0,
                trade.market_title,
                trade.market_slug,
                trade.market_icon,
                trade.event_id,
                trade.event_slug,
                trade.end_date,
                1 if trade.negative_risk else 0,
                trade.opposite_outcome,
                trade.opposite_asset,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def update_paper_trade_status(
        self,
        trade_id: int,
        status: str,
        exit_price: Decimal | None = None,
        pnl: Decimal | None = None,
    ) -> None:
        self.conn.execute(
            """UPDATE paper_trades
               SET status=?, exit_price=?, pnl=?, closed_at=?
               WHERE id=?""",
            (
                status,
                str(exit_price) if exit_price is not None else None,
                str(pnl) if pnl is not None else "0",
                _now_iso() if status == "closed" else None,
                trade_id,
            ),
        )
        self.conn.commit()

    def get_open_paper_trades(self) -> list[PaperTrade]:
        rows = self.conn.execute(
            """SELECT id, copied_from_wallet, market_condition_id, side, size,
                      entry_price, exit_price, status, pnl, opened_at, closed_at,
                      market_url, asset_token_id, wallet_avg_price, wallet_cur_price,
                      initial_value, current_value, total_bought, realized_pnl,
                      percent_pnl, percent_realized_pnl, redeemable, mergeable,
                      market_title, market_slug, market_icon, event_id, event_slug,
                      end_date, negative_risk, opposite_outcome, opposite_asset
               FROM paper_trades WHERE status='open'"""
        ).fetchall()
        return [
            PaperTrade(
                id=r[0],
                copied_from_wallet=r[1],
                market_condition_id=r[2],
                side=r[3],
                size=Decimal(r[4]),
                entry_price=Decimal(r[5]),
                exit_price=Decimal(r[6]) if r[6] else None,
                status=r[7],
                pnl=Decimal(r[8]),
                opened_at=datetime.fromisoformat(r[9]),
                closed_at=datetime.fromisoformat(r[10]) if r[10] else None,
                market_url=r[11] if r[11] else "",
                asset_token_id=r[12] if r[12] else "",
                wallet_avg_price=Decimal(r[13]) if r[13] else Decimal("0"),
                wallet_cur_price=Decimal(r[14]) if r[14] else Decimal("0"),
                initial_value=Decimal(r[15]) if r[15] else Decimal("0"),
                current_value=Decimal(r[16]) if r[16] else Decimal("0"),
                total_bought=Decimal(r[17]) if r[17] else Decimal("0"),
                realized_pnl=Decimal(r[18]) if r[18] else Decimal("0"),
                percent_pnl=Decimal(r[19]) if r[19] else Decimal("0"),
                percent_realized_pnl=Decimal(r[20]) if r[20] else Decimal("0"),
                redeemable=bool(r[21]),
                mergeable=bool(r[22]),
                market_title=r[23] if r[23] else "",
                market_slug=r[24] if r[24] else "",
                market_icon=r[25] if r[25] else "",
                event_id=r[26] if r[26] else "",
                event_slug=r[27] if r[27] else "",
                end_date=r[28] if r[28] else "",
                negative_risk=bool(r[29]),
                opposite_outcome=r[30] if r[30] else "",
                opposite_asset=r[31] if r[31] else "",
            )
            for r in rows
        ]

    def get_realized_pnl(self) -> Decimal:
        """Sum PnL from all closed trades."""
        row = self.conn.execute(
            "SELECT COALESCE(SUM(CAST(pnl AS REAL)), 0) FROM paper_trades WHERE status='closed'"
        ).fetchone()
        return Decimal(str(row[0]))

    def get_all_paper_trades(self, limit: int = 500) -> list[PaperTrade]:
        """Return the most recent `limit` paper trades ordered DESC by opened_at.

        `limit` is enforced at the SQL layer (LIMIT clause) — not post-fetch.
        """
        rows = self.conn.execute(
            """SELECT id, copied_from_wallet, market_condition_id, side, size,
                      entry_price, exit_price, status, pnl, opened_at, closed_at,
                      market_url, asset_token_id, wallet_avg_price, wallet_cur_price,
                      initial_value, current_value, total_bought, realized_pnl,
                      percent_pnl, percent_realized_pnl, redeemable, mergeable,
                      market_title, market_slug, market_icon, event_id, event_slug,
                      end_date, negative_risk, opposite_outcome, opposite_asset
               FROM paper_trades ORDER BY opened_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [
            PaperTrade(
                id=r[0],
                copied_from_wallet=r[1],
                market_condition_id=r[2],
                side=r[3],
                size=Decimal(r[4]),
                entry_price=Decimal(r[5]),
                exit_price=Decimal(r[6]) if r[6] else None,
                status=r[7],
                pnl=Decimal(r[8]),
                opened_at=datetime.fromisoformat(r[9]),
                closed_at=datetime.fromisoformat(r[10]) if r[10] else None,
                market_url=r[11] if r[11] else "",
                asset_token_id=r[12] if r[12] else "",
                wallet_avg_price=Decimal(r[13]) if r[13] else Decimal("0"),
                wallet_cur_price=Decimal(r[14]) if r[14] else Decimal("0"),
                initial_value=Decimal(r[15]) if r[15] else Decimal("0"),
                current_value=Decimal(r[16]) if r[16] else Decimal("0"),
                total_bought=Decimal(r[17]) if r[17] else Decimal("0"),
                realized_pnl=Decimal(r[18]) if r[18] else Decimal("0"),
                percent_pnl=Decimal(r[19]) if r[19] else Decimal("0"),
                percent_realized_pnl=Decimal(r[20]) if r[20] else Decimal("0"),
                redeemable=bool(r[21]),
                mergeable=bool(r[22]),
                market_title=r[23] if r[23] else "",
                market_slug=r[24] if r[24] else "",
                market_icon=r[25] if r[25] else "",
                event_id=r[26] if r[26] else "",
                event_slug=r[27] if r[27] else "",
                end_date=r[28] if r[28] else "",
                negative_risk=bool(r[29]),
                opposite_outcome=r[30] if r[30] else "",
                opposite_asset=r[31] if r[31] else "",
            )
            for r in rows
        ]

    # -- Account snapshot repository --

    def insert_account_snapshot(self, snapshot: AccountSnapshot) -> int:
        cursor = self.conn.execute(
            """INSERT INTO account_snapshots (equity, open_trades, total_pnl, snapshot_at)
               VALUES (?, ?, ?, ?)""",
            (
                str(snapshot.equity),
                snapshot.open_trades,
                str(snapshot.total_pnl),
                snapshot.snapshot_at.isoformat() if snapshot.snapshot_at else _now_iso(),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def get_latest_snapshot(self) -> AccountSnapshot | None:
        row = self.conn.execute(
            """SELECT id, equity, open_trades, total_pnl, snapshot_at
               FROM account_snapshots ORDER BY id DESC LIMIT 1"""
        ).fetchone()
        if row is None:
            return None
        return AccountSnapshot(
            id=row[0],
            equity=Decimal(row[1]),
            open_trades=row[2],
            total_pnl=Decimal(row[3]),
            snapshot_at=datetime.fromisoformat(row[4]),
        )

    def get_all_snapshots(self) -> list[AccountSnapshot]:
        """Return all snapshots ordered ASC by snapshot_at. Empty list when table empty."""
        rows = self.conn.execute(
            """SELECT id, equity, open_trades, total_pnl, snapshot_at
               FROM account_snapshots ORDER BY snapshot_at ASC"""
        ).fetchall()
        return [
            AccountSnapshot(
                id=row[0],
                equity=Decimal(row[1]),
                open_trades=row[2],
                total_pnl=Decimal(row[3]),
                snapshot_at=datetime.fromisoformat(row[4]),
            )
            for row in rows
        ]
