"""Discover top wallets from Polymarket leaderboard and write to Google Sheets.

This cronjob scrapes the Polymarket website leaderboard to find the top 20 wallets
by weekly PnL, stores them in SQLite, and updates the Google Sheets leaderboard.

Usage: uv run python -m copytrading.cronjobs.leaderboard_discovery
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

from copytrading.config import Settings
from copytrading.leaderboard_scraper import PolymarketLeaderboardScraper
from copytrading.models import Wallet
from copytrading.sheets_client import SheetsClient
from copytrading.store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    """Scrape Polymarket leaderboard and update database + Google Sheets."""
    logger.info("Starting leaderboard discovery")

    # Load settings
    settings = Settings.from_env()

    # Scrape leaderboard
    scraper = PolymarketLeaderboardScraper()
    entries = scraper.fetch_weekly_top(20)

    if not entries:
        logger.warning("No leaderboard entries found")
        return

    logger.info(f"Found {len(entries)} leaderboard entries")

    # Convert to Wallet objects and store in database
    now = datetime.now(UTC)
    wallets: list[Wallet] = []

    with Store() as store:
        for entry in entries:
            wallet = Wallet(
                address=entry.address,
                rank=entry.rank,
                total_pnl=Decimal(str(entry.pnl)),
                discovered_at=now,
                profile_url=entry.profile_url,
            )
            wallets.append(wallet)
            store.upsert_wallet(wallet)
            logger.info(
                f"Stored wallet #{entry.rank}: {entry.username} "
                f"(PnL: ${entry.pnl:,.2f}, Volume: ${entry.volume:,.2f})"
            )

    # Update Google Sheets
    try:
        sheets_client = SheetsClient.from_settings(settings)
        sheets_client.update_leaderboard(wallets)
        logger.info(f"Updated Google Sheets with {len(wallets)} wallets")
    except Exception as e:
        logger.error(f"Failed to update Google Sheets: {e}")

    logger.info("Leaderboard discovery completed")


if __name__ == "__main__":
    main()
