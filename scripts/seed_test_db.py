"""Seed a test SQLite DB so Playwright can verify populated panels.

Used only for visual testing; not part of the package. Run as::

    uv run python scripts/seed_test_db.py /tmp/dashboard_seed.db
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from copytrading.models import AccountSnapshot, Market, PaperTrade, Wallet
from copytrading.store import Store


def seed(db_path: Path) -> None:
    if db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with Store(db_path) as store:
        store.upsert_market(
            Market(
                condition_id="cond-test-1",
                question="Will Bitcoin hit 100k in 2024?",
                fetched_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )
        store.upsert_market(
            Market(
                condition_id="cond-test-2",
                question="Will the Fed cut rates in March?",
                fetched_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )
        store.upsert_wallet(
            Wallet(
                address="0xabcd1234567890abcdef",
                rank=1,
                total_pnl=Decimal("12500.50"),
                discovered_at=datetime(2024, 1, 1, tzinfo=UTC),
                last_checked_at=datetime.now(UTC),
                username="poly_whale",
            )
        )
        store.upsert_wallet(
            Wallet(
                address="0x9876fedcba0987654321",
                rank=2,
                total_pnl=Decimal("8200.75"),
                discovered_at=datetime(2024, 1, 1, tzinfo=UTC),
                last_checked_at=datetime.now(UTC),
                username="smart_money",
            )
        )
        now = datetime.now(UTC)
        for i, (cv, iv, opened_h, status, pnl) in enumerate(
            (
                (Decimal("120.00"), Decimal("100.00"), 24, "open", Decimal("0")),
                (Decimal("250.00"), Decimal("200.00"), 48, "open", Decimal("0")),
                (Decimal("80.00"), Decimal("100.00"), 72, "open", Decimal("0")),
                (Decimal("0"), Decimal("0"), 168, "closed", Decimal("150.00")),
                (Decimal("0"), Decimal("0"), 200, "closed", Decimal("-25.00")),
            )
        ):
            opened_at = now - timedelta(hours=opened_h)
            store.insert_paper_trade(
                PaperTrade(
                    copied_from_wallet="0xabcd1234567890abcdef",
                    market_condition_id="cond-test-1" if i < 3 else "cond-test-2",
                    side="yes",
                    size=Decimal("1"),
                    entry_price=Decimal("0.5"),
                    current_value=cv,
                    initial_value=iv,
                    status=status,
                    pnl=pnl,
                    market_title=("BTC 100k" if i < 3 else "Fed rates"),
                    opened_at=opened_at,
                    closed_at=opened_at if status == "closed" else None,
                )
            )
        for hours_ago in (24, 18, 12, 6, 1):
            store.insert_account_snapshot(
                AccountSnapshot(
                    equity=Decimal("201.20") + Decimal(hours_ago) * Decimal("0.5"),
                    open_trades=3,
                    total_pnl=Decimal("1.20"),
                    snapshot_at=now - timedelta(hours=hours_ago),
                )
            )


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/dashboard_seed.db")
    seed(target)
    print(f"Seeded {target}")
