"""Risk management for paper trading position sizing."""

from __future__ import annotations

from decimal import Decimal

DEFAULT_RISK_PCT = Decimal("0.005")  # 0.5%
MAX_EXPOSURE_PCT = Decimal("0.10")  # 10%


def calculate_position_size(
    account_equity: Decimal,
    risk_pct: Decimal = DEFAULT_RISK_PCT,
) -> Decimal:
    """Calculate the USDC amount to risk on a paper trade.

    Args:
        account_equity: Current paper account balance in USDC.
        risk_pct: Fraction of equity to risk (default 0.5%).

    Returns:
        Position size in USDC as Decimal.
    """
    return (account_equity * risk_pct).quantize(Decimal("0.01"))


def validate_trade(amount: Decimal, equity: Decimal) -> bool:
    """Check if a trade amount is within the 0.5% risk limit.

    Args:
        amount: Proposed trade size in USDC.
        equity: Current paper account balance in USDC.

    Returns:
        True if amount <= equity * 0.005.
    """
    max_size = equity * DEFAULT_RISK_PCT
    return amount <= max_size


def validate_exposure(
    current_exposure: Decimal, new_trade_size: Decimal, equity: Decimal
) -> bool:
    """Check if adding a new trade keeps total exposure within 10% of equity.

    Args:
        current_exposure: Sum of sizes of all open trades.
        new_trade_size: Size of the proposed new trade.
        equity: Current paper account balance in USDC.

    Returns:
        True if (current_exposure + new_trade_size) <= equity * 0.10.
    """
    max_exposure = equity * MAX_EXPOSURE_PCT
    return (current_exposure + new_trade_size) <= max_exposure
