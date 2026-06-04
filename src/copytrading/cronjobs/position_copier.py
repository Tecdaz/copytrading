"""Copy positions from tracked wallets as paper trades.

Usage: uv run python -m copytrading.cronjobs.position_copier
"""

from __future__ import annotations

import dataclasses
import logging
from datetime import UTC, datetime
from decimal import Decimal

from copytrading.config import Settings
from copytrading.models import AccountSnapshot, PaperTrade, Wallet
from copytrading.poly_client import PolyClient, PolyClientError
from copytrading.risk import (
    is_position_fresh,
    total_exposure,
    trade_value,
    validate_entry_price,
    validate_exposure,
)
from copytrading.sheets_client import SheetsClient
from copytrading.store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _get_real_exit_price(
    poly: PolyClient, store: Store, trade: PaperTrade
) -> tuple[Decimal, Decimal, bool]:
    """Get the real exit price for a closed trade via the CLOB midpoint.

    Looks up the market to find the right token_id (Yes/No), fetches its
    current midpoint price, and computes PnL as (exit - entry) * size.

    Args:
        poly: PolyClient instance.
        store: Store instance.
        trade: The closed trade.

    Returns:
        Tuple of (exit_price, pnl, used_real_exit).
        Falls back to entry_price / pnl=0 if market or midpoint unavailable.
    """
    try:
        market = store.get_market(trade.market_condition_id)
        if market is None:
            return trade.entry_price, Decimal("0"), False

        token_id = market.token_id_yes if trade.side.lower() == "yes" else market.token_id_no
        if not token_id:
            return trade.entry_price, Decimal("0"), False

        midpoint = poly.get_midpoint(token_id)
        pnl = (midpoint - trade.entry_price) * trade.size
        return midpoint, pnl, True

    except PolyClientError as e:
        logger.warning(
            "Failed to fetch real exit price for trade #%d: %s. Using entry as fallback.",
            trade.id,
            e,
        )
        return trade.entry_price, Decimal("0"), False


def copy_positions(poly: PolyClient, store: Store) -> tuple[list[PaperTrade], list[PaperTrade]]:
    """Compare API positions against open trades. Return (new, closed)."""
    wallets = store.get_all_wallets()
    if not wallets:
        logger.info("No wallets tracked — run leaderboard_discovery first")
        return [], []

    # Equity for position sizing
    snapshot = store.get_latest_snapshot()
    equity = snapshot.equity if snapshot else Decimal("200")
    logger.info("Current paper equity: %s USDC", equity)

    # Index open trades by (wallet, market, side)
    open_trades = store.get_open_paper_trades()
    open_by_key: dict[tuple[str, str, str], PaperTrade] = {
        (t.copied_from_wallet, t.market_condition_id, t.side): t for t in open_trades
    }

    new_trades: list[PaperTrade] = []
    seen_keys: set[tuple[str, str, str]] = set()
    current_exposure = total_exposure(open_trades)

    # --- Detect new positions across ALL wallets ---
    for wallet in wallets:
        try:
            positions = poly.get_positions(wallet.address)
        except PolyClientError as e:
            logger.warning("Failed to fetch positions for %s: %s", wallet.address, e)
            continue

        for pos in positions:
            key = (wallet.address, pos.market_condition_id, pos.side)
            seen_keys.add(key)

            if key in open_by_key:
                continue  # already tracking this position

            # Freshness check: skip stale positions (>1% price deviation)
            if not is_position_fresh(pos.avg_price, pos.current_price):
                logger.info(
                    "Skipping stale position for %s — price deviation > 1%%",
                    wallet.address,
                )
                continue

            # New position — ensure market exists in DB
            if not store.get_market(pos.market_condition_id):
                try:
                    market = poly.get_market(pos.market_condition_id)
                    store.upsert_market(market)
                except PolyClientError as e:
                    logger.warning(
                        "Failed to fetch market %s: %s",
                        pos.market_condition_id[:8],
                        e,
                    )
                    continue

            size = Decimal("1")

            # Fetch CLOB midpoint as entry price
            try:
                midpoint = poly.get_midpoint(pos.asset)
            except PolyClientError as e:
                logger.warning("Failed to fetch midpoint for %s: %s", pos.asset, e)
                continue

            # Validate entry price cap (≤ 0.5% equity)
            if not validate_entry_price(midpoint, equity):
                logger.warning(
                    "Skipping trade for %s — midpoint %s exceeds 0.5%% of equity %s",
                    wallet.address,
                    midpoint,
                    equity,
                )
                continue

            # Exposure is calculated as size × entry_price (equity at stake)
            new_trade_value = trade_value(size, midpoint)
            if not validate_exposure(current_exposure, new_trade_value, equity):
                logger.warning(
                    "Skipping trade for %s — total exposure would exceed 10%% of equity",
                    wallet.address,
                )
                continue

            trade = PaperTrade(
                copied_from_wallet=wallet.address,
                market_condition_id=pos.market_condition_id,
                side=pos.side,
                size=size,
                entry_price=midpoint,
                status="open",
                opened_at=datetime.now(UTC),
                market_url=f"https://polymarket.com/market/{pos.market_condition_id}",
                asset_token_id=pos.asset,
                wallet_avg_price=pos.avg_price,
                wallet_cur_price=pos.current_price,
                initial_value=pos.initial_value,
                current_value=pos.current_value,
                total_bought=pos.total_bought,
                realized_pnl=pos.realized_pnl,
                percent_pnl=pos.percent_pnl,
                percent_realized_pnl=pos.percent_realized_pnl,
                redeemable=pos.redeemable,
                mergeable=pos.mergeable,
                market_title=pos.title,
                market_slug=pos.slug,
                market_icon=pos.icon,
                event_id=pos.event_id,
                event_slug=pos.event_slug,
                end_date=pos.end_date,
                negative_risk=pos.negative_risk,
                opposite_outcome=pos.opposite_outcome,
                opposite_asset=pos.opposite_asset,
            )
            trade_id = store.insert_paper_trade(trade)
            trade = dataclasses.replace(trade, id=trade_id)
            new_trades.append(trade)
            current_exposure += new_trade_value
            logger.info(
                "Opened paper trade #%d: %s %s on %s (size=%s, price=%s)",
                trade_id,
                pos.side.upper(),
                pos.market_condition_id[:8],
                wallet.address[:8],
                size,
                pos.avg_price,
            )

    # --- Detect closed positions (across ALL wallets) ---
    closed_trades: list[PaperTrade] = []
    for key, trade in open_by_key.items():
        if key in seen_keys:
            continue  # position still open

        closed_at = datetime.now(UTC)

        # Fetch the real exit price from the market's midpoint
        exit_price, pnl, real_exit = _get_real_exit_price(poly, store, trade)

        store.update_paper_trade_status(
            trade.id,  # type: ignore[arg-type]
            "closed",
            exit_price=exit_price,
            pnl=pnl,
        )
        closed_trade = dataclasses.replace(
            trade,
            status="closed",
            exit_price=exit_price,
            pnl=pnl,
            closed_at=closed_at,
        )
        closed_trades.append(closed_trade)
        price_source = "midpoint" if real_exit else "entry (fallback)"
        logger.info(
            "Closed paper trade #%d: %s on %s | exit=%s (%s) | pnl=%s",
            trade.id,
            trade.market_condition_id[:8],
            trade.copied_from_wallet[:8],
            exit_price,
            price_source,
            pnl,
        )

    # --- Update wallet timestamps ---
    for wallet in wallets:
        updated = Wallet(
            address=wallet.address,
            rank=wallet.rank,
            total_pnl=wallet.total_pnl,
            discovered_at=wallet.discovered_at,
            last_checked_at=datetime.now(UTC),
        )
        store.upsert_wallet(updated)

    return new_trades, closed_trades


def update_live_positions(poly: PolyClient, store: Store, sheets: SheetsClient) -> None:
    """Rewrite the 'positions' tab with current prices and unrealized PnL.

    Fetches the midpoint for every open trade and writes a fresh row set
    to the same cells, so the sheet reflects live PnL every minute.
    """
    open_trades = store.get_open_paper_trades()
    if not open_trades:
        # Clear the tab with just the header so stale data doesn't linger
        sheets.update_live_positions([])
        return

    now = datetime.now(UTC)
    rows: list[list[str]] = []
    fallback_count = 0

    for trade in open_trades:
        current_price, _, used_real = _get_real_exit_price(poly, store, trade)
        if not used_real:
            fallback_count += 1
        unrealized_pnl = (current_price - trade.entry_price) * trade.size
        rows.append(
            [
                str(trade.id),
                trade.opened_at.isoformat() if trade.opened_at else "",
                trade.copied_from_wallet,
                trade.market_condition_id,
                trade.side,
                str(trade.size),
                str(trade.entry_price),
                str(current_price),
                str(unrealized_pnl),
                now.isoformat(),
                str(trade.wallet_avg_price),
                trade.asset_token_id,
            ]
        )

    sheets.update_live_positions(rows)
    if fallback_count:
        logger.warning(
            "Live positions: %d/%d trades using entry as fallback (no market/token)",
            fallback_count,
            len(open_trades),
        )
    logger.info("Live positions updated: %d rows", len(rows))


def run() -> None:
    """Main entry point for the position copier cronjob."""
    logger.info("Starting position copier")

    settings = Settings.from_env()
    poly = PolyClient()
    sheets = SheetsClient.from_settings(settings)
    sheets.ensure_history_header()
    sheets.ensure_positions_header()

    with Store() as store:
        new_trades, closed_trades = copy_positions(poly, store)

        if new_trades or closed_trades:
            sheets.append_trades(new_trades + closed_trades)

        update_live_positions(poly, store, sheets)

        # --- Update account balance every minute ---
        prev_snapshot = store.get_latest_snapshot()
        prev_equity = prev_snapshot.equity if prev_snapshot else Decimal("200")
        open_trades = store.get_open_paper_trades()
        total_unrealized_pnl = sum((t.pnl for t in open_trades), Decimal("0"))
        realized_pnl = store.get_realized_pnl()
        current_equity = prev_equity + total_unrealized_pnl + realized_pnl

        snapshot = AccountSnapshot(
            equity=current_equity,
            open_trades=len(open_trades),
            total_pnl=total_unrealized_pnl,
            snapshot_at=datetime.now(UTC),
        )
        store.insert_account_snapshot(snapshot)
        sheets.update_account(snapshot)
        logger.info("Account balance updated: equity=%s", snapshot.equity)

        logger.info(
            "Position copier done: %d new, %d closed",
            len(new_trades),
            len(closed_trades),
        )


if __name__ == "__main__":
    run()
