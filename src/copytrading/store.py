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
    last_checked_at TEXT
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
    closed_at TEXT
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
        self._conn = sqlite3.connect(self._db_path)
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
            """INSERT INTO wallets (address, rank, total_pnl, discovered_at, last_checked_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(address) DO UPDATE SET
                   rank=excluded.rank,
                   total_pnl=excluded.total_pnl,
                   last_checked_at=excluded.last_checked_at""",
            (
                wallet.address,
                wallet.rank,
                str(wallet.total_pnl),
                wallet.discovered_at.isoformat(),
                wallet.last_checked_at.isoformat() if wallet.last_checked_at else None,
            ),
        )
        self.conn.commit()

    def get_all_wallets(self) -> list[Wallet]:
        rows = self.conn.execute(
            "SELECT address, rank, total_pnl, discovered_at, last_checked_at "
            "FROM wallets ORDER BY rank"
        ).fetchall()
        return [
            Wallet(
                address=r[0],
                rank=r[1],
                total_pnl=Decimal(r[2]),
                discovered_at=datetime.fromisoformat(r[3]),
                last_checked_at=datetime.fromisoformat(r[4]) if r[4] else None,
            )
            for r in rows
        ]

    # -- Market repository --

    def upsert_market(self, market: Market) -> None:
        self.conn.execute(
            """INSERT INTO markets (condition_id, question, token_id_yes, token_id_no, active, fetched_at)
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
                entry_price, status, pnl, opened_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trade.copied_from_wallet,
                trade.market_condition_id,
                trade.side,
                str(trade.size),
                str(trade.entry_price),
                trade.status,
                str(trade.pnl),
                trade.opened_at.isoformat() if trade.opened_at else _now_iso(),
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
                      entry_price, exit_price, status, pnl, opened_at, closed_at
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
