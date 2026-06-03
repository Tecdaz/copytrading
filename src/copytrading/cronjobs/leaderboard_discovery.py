"""Discover top wallets from Polymarket leaderboard and write to Google Sheets.

This cronjob fetches the top 20 daily traders from the Polymarket data API,
stores them in SQLite, and updates the Google Sheets leaderboard.

Usage: uv run python -m copytrading.cronjobs.leaderboard_discovery
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

from copytrading.config import Settings
from copytrading.leaderboard_scraper import LeaderboardEntry
from copytrading.models import Wallet
from copytrading.poly_client import PolyClient, PolyClientError
from copytrading.sheets_client import SheetsClient
from copytrading.store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def fetch_top_traders(poly: PolyClient, limit: int = 20) -> list[LeaderboardEntry]:
    """Fetch top daily traders by volume with positive PnL from the Polymarket data API.

    Fetches the top 50 by daily volume (API max), filters for positive PnL,
    then returns the top `limit` (default 20) re-ranked by volume.

    Args:
        poly: PolyClient instance.
        limit: Max traders to return after filtering. Default 20.

    Returns:
        List of LeaderboardEntry sorted by daily volume, only positive PnL.
    """
    # Fetch max from API (50) ordered by volume, then filter for positive PnL
    raw_entries = poly.get_leaderboard(time_period="DAY", limit=50, order_by="VOL")

    entries: list[LeaderboardEntry] = []
    for raw in raw_entries:
        pnl = float(raw.get("pnl", 0))
        if pnl <= 0:
            continue  # Only traders with positive profit

        address = str(raw.get("proxyWallet", ""))
        if not address:
            continue

        username = str(raw.get("userName", f"{address[:10]}..."))
        volume = float(raw.get("vol", 0))

        entries.append(
            LeaderboardEntry(
                address=address.lower(),
                username=username,
                pnl=pnl,
                volume=volume,
                profile_url=f"https://polymarket.com/profile/{address.lower()}",
            )
        )

    # Re-rank by volume and take top N
    entries.sort(key=lambda e: e.volume, reverse=True)
    top = entries[:limit]
    for i, entry in enumerate(top, start=1):
        entry.rank = i  # type: ignore[misc]

    return top


def main() -> None:
    """Fetch top daily traders and update database + Google Sheets."""
    logger.info("Starting leaderboard discovery")

    # Load settings
    settings = Settings.from_env()

    # Fetch top daily traders
    poly = PolyClient()
    try:
        entries = fetch_top_traders(poly, limit=20)
    except PolyClientError as e:
        logger.error("Failed to fetch leaderboard: %s", e)
        return

    if not entries:
        logger.warning("No leaderboard entries found")
        return

    logger.info(f"Found {len(entries)} daily top traders")

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
