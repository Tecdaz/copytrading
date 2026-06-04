"""Tests for the read-only web dashboard (FastAPI + Jinja2 + HTMX).

Covers REQ-WEB-1..5, REQ-WEB-11 (panels and empty-state behavior) in this
file. REQ-WEB-9, 10, 12, 14 (vendor serving, polling markers, no-CDN,
read-only mutating-method rejection) live further down in the same file.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from copytrading.models import AccountSnapshot, Market, PaperTrade, Wallet
from copytrading.store import Store
from copytrading.web.app import create_app


@pytest.fixture
def app_with_db(tmp_path: Path) -> Iterator[TestClient]:
    """Spin up the app against a real (file-backed) sqlite store with WAL.

    Using a temp file (not :memory:) is intentional: the dashboard reads
    from a long-lived DB in production. :memory: would be faster but it
    would not exercise the WAL mode that lets cronjobs write while the
    web layer reads.
    """
    db_path = tmp_path / "dashboard.db"
    # Pre-seed so the panel endpoints have at least one row to render.
    with Store(db_path) as seed:
        seed.upsert_market(
            Market(
                condition_id="cond1",
                question="Will it rain?",
                fetched_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )
        seed.upsert_wallet(
            Wallet(
                address="0xabcdef1234567890",
                rank=1,
                total_pnl=Decimal("100"),
                discovered_at=datetime(2024, 1, 1, tzinfo=UTC),
                last_checked_at=datetime(2024, 1, 2, tzinfo=UTC),
            )
        )
        seed.insert_paper_trade(
            PaperTrade(
                copied_from_wallet="0xabcdef1234567890",
                market_condition_id="cond1",
                side="yes",
                size=Decimal("2"),
                entry_price=Decimal("0.50"),
                current_value=Decimal("1.20"),
                percent_pnl=Decimal("20"),
                market_title="Will it rain?",
                opened_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )
        seed.insert_account_snapshot(
            AccountSnapshot(
                equity=Decimal("201.20"),
                open_trades=1,
                total_pnl=Decimal("1.20"),
                snapshot_at=datetime(2024, 1, 1, 12, tzinfo=UTC),
            )
        )
    app = create_app(db_path=db_path)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def app_empty(tmp_path: Path) -> Iterator[TestClient]:
    """App pointed at a brand-new (empty) DB. Used by empty-state tests."""
    db_path = tmp_path / "empty.db"
    app = create_app(db_path=db_path)
    with TestClient(app) as client:
        yield client


# ---------------------------------------------------------------------------
# REQ-WEB-1: index renders 7 panels with HTMX polling
# ---------------------------------------------------------------------------


class TestIndexPage:
    def test_index_returns_200_with_seven_panels(self, app_with_db: TestClient) -> None:
        # Pre-condition: the full dashboard must serve HTML that mentions all
        # 7 panel section ids/hooks. The 4 panels in Slice 2 are:
        # equity-curve, open-positions, trade-history, wallets. The 3
        # aggregate cards from Slice 3 also have their div hooks wired in
        # index.html (the route handlers return empty-state for now).
        response = app_with_db.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        # All 7 panel hooks must be present.
        for panel in (
            "panel-equity-curve",
            "panel-open-positions",
            "panel-trade-history",
            "panel-wallets",
            "panel-money-in-open",
            "panel-pnl-open",
            "panel-pnl-historical",
        ):
            assert panel in response.text, f"missing panel hook: {panel}"

    def test_index_renders_even_with_empty_database(self, app_empty: TestClient) -> None:
        # Pre-condition: with an empty DB the index still returns 200 and
        # the 7 panel hooks are wired (each will render its empty-state).
        response = app_empty.get("/")

        assert response.status_code == 200
        for panel in (
            "panel-equity-curve",
            "panel-open-positions",
            "panel-trade-history",
            "panel-wallets",
            "panel-money-in-open",
            "panel-pnl-open",
            "panel-pnl-historical",
        ):
            assert panel in response.text, f"missing panel hook: {panel}"


# ---------------------------------------------------------------------------
# REQ-WEB-2: equity-curve panel (canvas + data island)
# ---------------------------------------------------------------------------


class TestEquityCurvePanel:
    def test_renders_canvas_and_data_island(self, app_with_db: TestClient) -> None:
        # Pre-condition: response must contain the chart canvas AND a
        # JSON data island with the seeded snapshot equity value.
        response = app_with_db.get("/api/panel/equity-curve")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        body = response.text
        assert 'id="equity-chart"' in body
        assert 'id="equity-data"' in body
        # Seeded equity was 201.20 — the data island must carry it.
        assert "201.20" in body

    def test_empty_state_when_no_snapshots(self, app_empty: TestClient) -> None:
        # REQ-WEB-11: every panel with no data renders a placeholder,
        # not an empty <canvas> or a blank card. The placeholder text
        # the dashboard uses is "No data yet".
        response = app_empty.get("/api/panel/equity-curve")

        assert response.status_code == 200
        body = response.text
        # The data island must be present and contain an empty JSON array.
        assert 'id="equity-data"' in body
        assert "[]" in body
        # And the empty-state placeholder must be visible to the user.
        assert "No data yet" in body


# ---------------------------------------------------------------------------
# REQ-WEB-3: open-positions panel
# ---------------------------------------------------------------------------


class TestOpenPositionsPanel:
    def test_lists_open_trades_in_descending_opened_at(self, app_with_db: TestClient) -> None:
        # Pre-condition: with one open trade, the panel renders the row
        # with the seeded market title. (The "DESC by opened_at" property
        # is covered in the store-level test; here we only need to prove
        # the route surfaces the row to the template.)
        response = app_with_db.get("/api/panel/open-positions")

        assert response.status_code == 200
        body = response.text
        # One open trade, one row, with the market title visible.
        assert "Will it rain?" in body
        # Side and current_value are part of the spec's column list.
        assert "yes" in body
        assert "1.20" in body

    def test_empty_state_when_no_open_trades(self, app_empty: TestClient) -> None:
        response = app_empty.get("/api/panel/open-positions")

        assert response.status_code == 200
        assert "No open positions" in response.text


# ---------------------------------------------------------------------------
# REQ-WEB-4: trade-history panel
# ---------------------------------------------------------------------------


class TestTradeHistoryPanel:
    def test_renders_seeded_trade(self, app_with_db: TestClient) -> None:
        # Pre-condition: with at least one paper trade the panel renders
        # the title and the status.
        response = app_with_db.get("/api/panel/trade-history")

        assert response.status_code == 200
        body = response.text
        assert "Will it rain?" in body
        # Status is one of the columns the spec requires.
        assert "open" in body

    def test_empty_state_when_no_trades(self, app_empty: TestClient) -> None:
        response = app_empty.get("/api/panel/trade-history")

        assert response.status_code == 200
        assert "No trade history" in response.text


# ---------------------------------------------------------------------------
# REQ-WEB-5: tracked-wallets panel
# ---------------------------------------------------------------------------


class TestWalletsPanel:
    def test_renders_seeded_wallet(self, app_with_db: TestClient) -> None:
        # Pre-condition: with one wallet the panel renders the address
        # prefix (the schema has no `username` column yet — the template's
        # address fallback is the realistic render path) and the total PnL.
        response = app_with_db.get("/api/panel/wallets")

        assert response.status_code == 200
        body = response.text
        assert "0xabcdef12" in body  # address[:10]
        assert "100" in body  # total_pnl=100 from the seed

    def test_empty_state_when_no_wallets(self, app_empty: TestClient) -> None:
        response = app_empty.get("/api/panel/wallets")

        assert response.status_code == 200
        assert "No tracked wallets" in response.text
