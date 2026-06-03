"""Domain models for the paper copy trader."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class Wallet:
    """A tracked wallet from the leaderboard."""

    address: str
    rank: int
    total_pnl: Decimal
    discovered_at: datetime
    last_checked_at: datetime | None = None
    profile_url: str = ""


@dataclass(frozen=True)
class Market:
    """A Polymarket prediction market."""

    condition_id: str
    question: str
    token_id_yes: str | None = None
    token_id_no: str | None = None
    active: bool = True
    fetched_at: datetime | None = None


@dataclass(frozen=True)
class Position:
    """A wallet's position in a market."""

    wallet_address: str
    market_condition_id: str
    side: str  # "yes" or "no" or outcome name
    size: Decimal
    avg_price: Decimal
    outcome_index: int = 0  # 0 or 1
    current_price: Decimal = Decimal("0")
    initial_value: Decimal = Decimal("0")
    current_value: Decimal = Decimal("0")
    cash_pnl: Decimal = Decimal("0")
    title: str = ""
    fetched_at: datetime | None = None


@dataclass(frozen=True)
class PaperTrade:
    """A simulated paper trade (NOT a real trade)."""

    copied_from_wallet: str
    market_condition_id: str
    side: str  # "yes" or "no"
    size: Decimal
    entry_price: Decimal
    status: str = "open"  # "open" or "closed"
    pnl: Decimal = Decimal("0")
    exit_price: Decimal | None = None
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    market_url: str = ""
    id: int | None = None


@dataclass(frozen=True)
class AccountSnapshot:
    """Point-in-time snapshot of the paper trading account."""

    equity: Decimal
    open_trades: int
    total_pnl: Decimal = Decimal("0")
    snapshot_at: datetime | None = None
    id: int | None = None
