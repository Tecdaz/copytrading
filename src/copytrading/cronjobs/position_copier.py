"""Copy positions from tracked wallets as paper trades.

Usage: uv run python -m copytrading.cronjobs.position_copier
"""

from __future__ import annotations

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

# Check for positions opened/closed in the last N seconds
CHECK_WINDOW_SECONDS = 60


def run() -> None:
    """Main entry point for the position copier cronjob."""
    logger.info("Starting position copier")

    settings = Settings.from_env()
    poly = PolyClient()
    sheets = SheetsClient.from_settings(settings)
    sheets.ensure_history_header()

    with Store() as store:
        # Get current account equity
        snapshot = store.get_latest_snapshot()
        equity = snapshot.equity if snapshot else Decimal("200")
        logger.info("Current paper equity: %s USDC", equity)

        # Get all tracked wallets
        wallets = store.get_all_wallets()
        if not wallets:
            logger.info("No wallets tracked — run leaderboard_discovery first")
            return

        # Get open paper trades to detect closures
        open_trades = store.get_open_paper_trades()
        open_by_key = {
            (t.copied_from_wallet, t.market_condition_id, t.side): t for t in open_trades
        }

        new_trades: list[PaperTrade] = []
        closed_trades: list[PaperTrade] = []

        for wallet in wallets:
            try:
                positions = poly.get_positions(wallet.address)
            except PolyClientError as e:
                logger.warning("Failed to fetch positions for %s: %s", wallet.address, e)
                continue

            # Track which positions we've seen
            seen_keys: set[tuple[str, str, str]] = set()

            for pos in positions:
                key = (wallet.address, pos.market_condition_id, pos.side)
                seen_keys.add(key)

                if key not in open_by_key:
                    # New position — open a paper trade
                    
                    # Ensure market exists in database
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

            # Check for closed positions
            for key, trade in open_by_key.items():
                if key[0] == wallet.address and key not in seen_keys:
                    # Position was closed by the trader
                    # For paper trading, we'd need the exit price from the market
                    # Using entry price as placeholder (real impl would fetch current price)
                    store.update_paper_trade_status(
                        trade.id,  # type: ignore[arg-type]
                        "closed",
                        exit_price=trade.entry_price,  # placeholder
                        pnl=Decimal("0"),  # placeholder
                    )
                    closed_trades.append(trade)
                    logger.info(
                        "Closed paper trade #%d: %s on %s",
                        trade.id,
                        trade.market_condition_id[:8],
                        wallet.address[:8],
                    )

            # Update wallet last_checked_at
            updated_wallet = Wallet(
                address=wallet.address,
                rank=wallet.rank,
                total_pnl=wallet.total_pnl,
                discovered_at=wallet.discovered_at,
                last_checked_at=datetime.now(UTC),
            )
            store.upsert_wallet(updated_wallet)

    # Append new trades to Google Sheets history
    if new_trades:
        sheets.append_trades(new_trades)
        logger.info("Appended %d new trades to history", len(new_trades))

    logger.info(
        "Position copier complete: %d opened, %d closed",
        len(new_trades),
        len(closed_trades),
    )


if __name__ == "__main__":
    run()
