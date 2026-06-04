"""Risk management for paper trading position sizing."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Any

DEFAULT_RISK_PCT = Decimal("0.005")  # 0.5%
MAX_EXPOSURE_PCT = Decimal("0.10")  # 10%


def trade_value(size: Decimal, entry_price: Decimal) -> Decimal:
    """Compute the equity-at-stake for a single trade.

    Equity at stake is the notional exposure tied up in a position,
    calculated as size × entry_price. A trade entered at 0.50 with $1 size
    represents $0.50 of equity at stake; at 0.95 it's $0.95.

    Args:
        size: Trade size in USDC.
        entry_price: Price per share at entry (0.0 to 1.0).

    Returns:
        Equity at stake as Decimal.
    """
    return (size * entry_price).quantize(Decimal("0.01"))


def total_exposure(open_trades: Iterable[Any]) -> Decimal:
    """Sum equity-at-stake across all open trades.

    Args:
        open_trades: Iterable of objects with `size` and `entry_price` attributes.

    Returns:
        Total exposure as Decimal.
    """
    return sum((trade_value(t.size, t.entry_price) for t in open_trades), Decimal("0"))


def validate_exposure(current_exposure: Decimal, new_trade_value: Decimal, equity: Decimal) -> bool:
    """Check if adding a new trade keeps total exposure within 10% of equity.

    Args:
        current_exposure: Sum of equity-at-stake for all open trades.
        new_trade_value: Equity-at-stake of the proposed new trade.
        equity: Current paper account balance in USDC.

    Returns:
        True if (current_exposure + new_trade_value) <= equity * 0.10.
    """
    max_exposure = equity * MAX_EXPOSURE_PCT
    return (current_exposure + new_trade_value) <= max_exposure


def is_position_fresh(avg_price: Decimal, cur_price: Decimal) -> bool:
    """Check if a position's price deviation is within 1%.

    Returns True if |avgPrice - curPrice| / avgPrice <= 0.01.
    Handles avg_price == 0 gracefully (returns False).

    Args:
        avg_price: The wallet's average entry price.
        cur_price: The current market price.

    Returns:
        True if the position is fresh enough to copy.
    """
    if avg_price == 0:
        return False
    deviation = abs(avg_price - cur_price) / avg_price
    return deviation <= Decimal("0.01")


def validate_entry_price(entry_price: Decimal, equity: Decimal) -> bool:
    """Check that the entry price does not exceed 0.5% of equity.

    Args:
        entry_price: The proposed entry price (CLOB midpoint).
        equity: Current paper account balance in USDC.

    Returns:
        True if entry_price <= equity * 0.005.
    """
    if equity == 0:
        return False
    return entry_price <= equity * Decimal("0.005")
