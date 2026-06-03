"""Copy positions from tracked wallets as paper trades.

Usage: uv run python -m copytrading.cronjobs.position_copier
"""

from __future__ import annotations

import dataclasses
import logging
from datetime import UTC, datetime
from decimal import Decimal

from copytrading.config import Settings
from copytrading.models import PaperTrade, Wallet
from copytrading.poly_client import PolyClient, PolyClientError
from copytrading.risk import calculate_position_size, validate_trade
from copytrading.sheets_client import SheetsClient
from copytrading.store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def copy_positions(
    poly: PolyClient, store: Store
) -> tuple[list[PaperTrade], list[PaperTrade]]:
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

            size = calculate_position_size(equity)
            if not validate_trade(size, equity):
                logger.warning(
                    "Skipping trade for %s — size %s exceeds risk limit",
                    wallet.address,
                    size,
                )
                continue

            trade = PaperTrade(
                copied_from_wallet=wallet.address,
                market_condition_id=pos.market_condition_id,
                side=pos.side,
                size=size,
                entry_price=pos.avg_price,
                status="open",
                opened_at=datetime.now(UTC),
            )
            trade_id = store.insert_paper_trade(trade)
            trade = dataclasses.replace(trade, id=trade_id)
            new_trades.append(trade)
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
        store.update_paper_trade_status(
            trade.id,  # type: ignore[arg-type]
            "closed",
            exit_price=trade.entry_price,  # placeholder — real impl fetches current price
            pnl=Decimal("0"),  # placeholder
        )
        closed_trade = dataclasses.replace(
            trade,
            status="closed",
            exit_price=trade.entry_price,
            pnl=Decimal("0"),
            closed_at=closed_at,
        )
        closed_trades.append(closed_trade)
        logger.info(
            "Closed paper trade #%d: %s on %s",
            trade.id,
            trade.market_condition_id[:8],
            trade.copied_from_wallet[:8],
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


def run() -> None:
    """Main entry point for the position copier cronjob."""
    logger.info("Starting position copier")

    settings = Settings.from_env()
    poly = PolyClient()
    sheets = SheetsClient.from_settings(settings)
    sheets.ensure_history_header()

    with Store() as store:
        new_trades, closed_trades = copy_positions(poly, store)

        if new_trades or closed_trades:
            sheets.append_trades(new_trades + closed_trades)

        logger.info(
            "Position copier done: %d new, %d closed",
            len(new_trades),
            len(closed_trades),
        )


if __name__ == "__main__":
    run()
