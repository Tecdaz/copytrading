"""Track account status and update Google Sheets.

Usage: uv run python -m copytrading.cronjobs.account_tracker
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

from copytrading.config import Settings
from copytrading.models import AccountSnapshot
from copytrading.sheets_client import SheetsClient
from copytrading.store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

INITIAL_EQUITY = Decimal("200")


def run() -> None:
    """Main entry point for the account tracker cronjob."""
    logger.info("Starting account tracker")

    settings = Settings.from_env()
    sheets = SheetsClient.from_settings(settings)

    with Store() as store:
        # Get previous snapshot
        prev_snapshot = store.get_latest_snapshot()
        prev_equity = prev_snapshot.equity if prev_snapshot else INITIAL_EQUITY

        # Calculate current equity from open trades
        open_trades = store.get_open_paper_trades()
        total_unrealized_pnl = sum((t.pnl for t in open_trades), Decimal("0"))

        # Get realized PnL from closed trades
        realized_pnl = store.get_realized_pnl()
        current_equity = prev_equity + total_unrealized_pnl + realized_pnl

        # Create new snapshot
        snapshot = AccountSnapshot(
            equity=current_equity,
            open_trades=len(open_trades),
            total_pnl=total_unrealized_pnl,
            snapshot_at=datetime.now(UTC),
        )
        store.insert_account_snapshot(snapshot)

        logger.info(
            "Account snapshot: equity=%s, open_trades=%d, unrealized_pnl=%s, realized_pnl=%s",
            snapshot.equity,
            snapshot.open_trades,
            snapshot.total_pnl,
            realized_pnl,
        )

    # Update Google Sheets
    sheets.update_account(snapshot)
    logger.info("Updated account sheet")

    logger.info("Account tracker complete")


if __name__ == "__main__":
    run()
