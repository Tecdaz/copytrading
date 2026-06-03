"""Discover top wallets from Polymarket and write to leaderboard sheet.

Usage: uv run python -m copytrading.cronjobs.leaderboard_discovery
"""

from __future__ import annotations

import logging

from copytrading.config import Settings
from copytrading.models import Wallet
from copytrading.poly_client import PolyClient
from copytrading.sheets_client import SheetsClient
from copytrading.store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TOP_N = 20


def discover_leaderboard() -> list[Wallet]:
    """Fetch markets, aggregate wallet PnL, return top N wallets.

    Since Polymarket's public API doesn't have a direct 'top traders' endpoint,
    we fetch active markets and extract unique wallet addresses from positions.
    In production, this would use a leaderboard API or scrape from the website.
    """
    poly = PolyClient()

    # For now, fetch markets to verify API connectivity
    markets = poly.get_markets()
    logger.info("Fetched %d markets from Polymarket", len(markets))

    # Placeholder: In a real implementation, we'd aggregate wallet PnL
    # from multiple sources. For paper trading demo, we return empty
    # and rely on manually-added wallets via the store.
    return []


def run() -> None:
    """Main entry point for the leaderboard discovery cronjob."""
    logger.info("Starting leaderboard discovery")

    settings = Settings.from_env()
    poly = PolyClient()
    sheets = SheetsClient.from_settings(settings)

    # Verify API connectivity
    markets = poly.get_markets()
    logger.info("Polymarket API OK — %d active markets", len(markets))

    # Discover top wallets
    wallets = discover_leaderboard()

    # Update store
    with Store() as store:
        for w in wallets:
            store.upsert_wallet(w)

        # Also get any previously tracked wallets
        all_wallets = store.get_all_wallets()

    # Update Google Sheets leaderboard
    if all_wallets:
        sheets.update_leaderboard(all_wallets)
        logger.info("Updated leaderboard with %d wallets", len(all_wallets))
    else:
        logger.info("No wallets to update in leaderboard")

    logger.info("Leaderboard discovery complete")


if __name__ == "__main__":
    run()
