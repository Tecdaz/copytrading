"""Tests for the read-only web dashboard (FastAPI + Jinja2 + HTMX).

Covers REQ-WEB-1..5, REQ-WEB-11 (panels and empty-state behavior) in the
``TestIndexPage`` / ``Test<Panel>Panel`` classes below. REQ-WEB-9, 10, 12,
14 (vendor serving, polling markers, no-CDN, read-only mutating-method
rejection, CSS markers) live in ``TestServingAndBind`` further down.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from copytrading.models import AccountSnapshot, Market, PaperTrade, Wallet
from copytrading.store import Store
from copytrading.web.app import create_app
from copytrading.web.formatting import format_signed


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


# ---------------------------------------------------------------------------
# REQ-WEB-7 / REQ-WEB-9 / REQ-WEB-10 / REQ-WEB-12 / REQ-WEB-14
# Serving, polling, no-CDN, CSS markers, mutating-method rejection
# ---------------------------------------------------------------------------


class TestServingAndBind:
    def test_vendor_chart_umd_is_served_from_static(self, app_with_db: TestClient) -> None:
        # REQ-WEB-9: the vendored Chart.js file must be served by the app
        # (not pulled from a CDN at runtime). The asset is bytes; we just
        # verify the route returns 200 with text/javascript and a non-empty
        # body so a browser can execute it.
        response = app_with_db.get("/static/vendor/chart.umd.min.js")

        assert response.status_code == 200
        assert "javascript" in response.headers["content-type"]
        assert len(response.content) > 0

    def test_index_contains_every_5s_trigger_at_least_7_times(
        self, app_with_db: TestClient
    ) -> None:
        # REQ-WEB-7: each of the 7 panel placeholders polls every 5s.
        # The literal ``every 5s`` string must appear at least 7 times.
        response = app_with_db.get("/")

        assert response.status_code == 200
        assert response.text.count("every 5s") >= 7

    def test_index_does_not_reference_cdn_hosts(self, app_with_db: TestClient) -> None:
        # REQ-WEB-9: the dashboard MUST NOT issue a network request to a
        # public CDN at runtime. The vendored HTMX + Chart.js assets are
        # the only JS sources, both served from /static/vendor/.
        response = app_with_db.get("/")
        body = response.text

        for forbidden in (
            "cdn.jsdelivr.net",
            "unpkg.com",
            "cdnjs.cloudflare.com",
        ):
            assert forbidden not in body, f"index references CDN host: {forbidden}"

    def test_post_to_index_is_rejected_with_405(self, app_with_db: TestClient) -> None:
        # REQ-WEB-14: the dashboard exposes only GET handlers; mutating
        # methods on any path return 405 Method Not Allowed.
        for path in ("/", "/api/panel/equity-curve", "/api/panel/wallets"):
            response = app_with_db.post(path)

            assert response.status_code == 405, (
                f"POST {path} should be 405, got {response.status_code}"
            )

    def test_css_includes_neon_and_monospace_markers(self, app_with_db: TestClient) -> None:
        # REQ-WEB-12: the stylesheet must carry the visual markers
        # (monospace font-family + a cyan or violet hex color). These are
        # the semantic markers a reviewer checks without opening devtools.
        response = app_with_db.get("/static/css/dashboard.css")

        assert response.status_code == 200
        assert "text/css" in response.headers["content-type"]
        body = response.text
        # Monospace font-family is required for the .number class.
        assert "font-family" in body
        assert any(token in body for token in ("JetBrains Mono", "Fira Code", "monospace")), (
            "CSS missing monospace font-family token"
        )
        # A cyan or violet hex color must be present (any of the spec's
        # accepted values).
        assert any(token in body for token in ("#0ff", "#0ea5e9", "#8b5cf6", "#a855f7")), (
            "CSS missing cyan or violet hex color"
        )


# ---------------------------------------------------------------------------
# REQ-WEB-13: default bind address is loopback (127.0.0.1, not 0.0.0.0)
# ---------------------------------------------------------------------------


class TestBindAddress:
    def test_main_module_passes_loopback_host(self) -> None:
        # REQ-WEB-13: the entrypoint MUST bind to 127.0.0.1 (loopback) by
        # default and never to 0.0.0.0. The contract lives in
        # :mod:`copytrading.web.__main__`, which we invoke via runpy.
        from copytrading.web import __main__ as web_main

        with (
            mock.patch.object(web_main.uvicorn, "run") as mock_run,
            mock.patch.object(web_main, "__name__", "__main__"),
        ):
            # Direct call: runpy only re-runs the module when it sees
            # __name__ == "__main__"; we already patched the attribute,
            # so calling main() is equivalent.
            web_main.main()

        assert mock_run.call_count == 1
        call = mock_run.call_args
        # uvicorn.run may be called positionally or with kwargs; we accept
        # both and look for host= in the merged args.
        merged = {**call.kwargs}
        # First positional may be the app reference; the bind args must
        # still appear as kwargs.
        assert merged.get("host") == "127.0.0.1", f"expected host='127.0.0.1', got call={call}"
        assert merged.get("port") == 8000
        # Defense-in-depth: bind must not be 0.0.0.0 anywhere.
        assert "0.0.0.0" not in str(call)


# ---------------------------------------------------------------------------
# Slice 3 aggregate-card fixtures + tests
# REQ-WEB-6, REQ-WEB-7, REQ-WEB-8
# ---------------------------------------------------------------------------


def _seed_market_and_wallet(store: Store) -> None:
    """Insert the FK parents a paper_trade needs (market + wallet)."""
    store.upsert_market(
        Market(
            condition_id="cond-agg",
            question="Aggregate card fixture market",
            fetched_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
    )
    store.upsert_wallet(
        Wallet(
            address="0xagg1234567890",
            rank=1,
            total_pnl=Decimal("0"),
            discovered_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
    )


@pytest.fixture
def app_money_in_open_populated(tmp_path: Path) -> Iterator[TestClient]:
    """Two open trades for money-in-open (REQ-WEB-6 happy path).

    current_value = 1.00 and 2.50 → sum = 3.50.
    """
    db_path = tmp_path / "money_in_open.db"
    with Store(db_path) as seed:
        _seed_market_and_wallet(seed)
        for cv, iv, opened in (
            (Decimal("1.00"), Decimal("1.00"), datetime(2024, 1, 1, tzinfo=UTC)),
            (Decimal("2.50"), Decimal("2.00"), datetime(2024, 1, 2, tzinfo=UTC)),
        ):
            seed.insert_paper_trade(
                PaperTrade(
                    copied_from_wallet="0xagg1234567890",
                    market_condition_id="cond-agg",
                    side="yes",
                    size=Decimal("1"),
                    entry_price=Decimal("0.5"),
                    current_value=cv,
                    initial_value=iv,
                    market_title="Aggregate fixture",
                    opened_at=opened,
                )
            )
    app = create_app(db_path=db_path)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def app_pnl_open_populated(tmp_path: Path) -> Iterator[TestClient]:
    """Two open trades for pnl-open (REQ-WEB-7 happy path).

    (cv=2.00, iv=1.00) → unrealized = +1.00
    (cv=0.80, iv=1.00) → unrealized = -0.20
    sum = +0.80 (signed).
    """
    db_path = tmp_path / "pnl_open.db"
    with Store(db_path) as seed:
        _seed_market_and_wallet(seed)
        seed.insert_paper_trade(
            PaperTrade(
                copied_from_wallet="0xagg1234567890",
                market_condition_id="cond-agg",
                side="yes",
                size=Decimal("1"),
                entry_price=Decimal("0.5"),
                current_value=Decimal("2.00"),
                initial_value=Decimal("1.00"),
                market_title="Pnl-open A",
                opened_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )
        seed.insert_paper_trade(
            PaperTrade(
                copied_from_wallet="0xagg1234567890",
                market_condition_id="cond-agg",
                side="yes",
                size=Decimal("1"),
                entry_price=Decimal("0.5"),
                current_value=Decimal("0.80"),
                initial_value=Decimal("1.00"),
                market_title="Pnl-open B",
                opened_at=datetime(2024, 1, 2, tzinfo=UTC),
            )
        )
    app = create_app(db_path=db_path)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def app_pnl_historical_populated(tmp_path: Path) -> Iterator[TestClient]:
    """Two closed trades for pnl-historical (REQ-WEB-8 happy path).

    pnl = 1.50 and -0.25 → sum = +1.25 (signed).
    """
    db_path = tmp_path / "pnl_historical.db"
    with Store(db_path) as seed:
        _seed_market_and_wallet(seed)
        for pnl, opened in (
            (Decimal("1.50"), datetime(2024, 1, 1, tzinfo=UTC)),
            (Decimal("-0.25"), datetime(2024, 1, 2, tzinfo=UTC)),
        ):
            seed.insert_paper_trade(
                PaperTrade(
                    copied_from_wallet="0xagg1234567890",
                    market_condition_id="cond-agg",
                    side="yes",
                    size=Decimal("1"),
                    entry_price=Decimal("0.5"),
                    status="closed",
                    pnl=pnl,
                    market_title="Historical fixture",
                    opened_at=opened,
                    closed_at=opened,
                )
            )
    app = create_app(db_path=db_path)
    with TestClient(app) as client:
        yield client


# ---------------------------------------------------------------------------
# REQ-WEB-6: money-in-open card — SUM(CAST(current_value AS REAL)) open trades
# ---------------------------------------------------------------------------


class TestMoneyInOpenPanel:
    def test_sums_current_value_of_open_trades(
        self, app_money_in_open_populated: TestClient
    ) -> None:
        # REQ-WEB-6 happy path: 2 open trades with current_value 1.00 and
        # 2.50 must produce the literal "3.50" in the response. The route
        # uses SUM(CAST(current_value AS REAL)) per spec wording.
        response = app_money_in_open_populated.get("/api/panel/money-in-open")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "3.50" in response.text

    def test_shows_zero_when_no_open_trades(self, app_empty: TestClient) -> None:
        # REQ-WEB-6 empty path: no open trades → SUM returns NULL → "0.00".
        # Per spec the empty-state value is "0.00" (not an empty placeholder
        # — the value is the sum, which is genuinely 0).
        response = app_empty.get("/api/panel/money-in-open")

        assert response.status_code == 200
        assert "0.00" in response.text


# ---------------------------------------------------------------------------
# REQ-WEB-7: pnl-open card — signed SUM(current_value - initial_value) open
# ---------------------------------------------------------------------------


class TestPnlOpenPanel:
    def test_computes_signed_unrealized_pnl(self, app_pnl_open_populated: TestClient) -> None:
        # REQ-WEB-7 happy path: 2 open trades (cv=2.00,iv=1.00) and
        # (cv=0.80,iv=1.00) → sum of (current-initial) = +0.80. The
        # signed format ("+0.80") is the spec-mandated output.
        response = app_pnl_open_populated.get("/api/panel/pnl-open")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "+0.80" in response.text

    def test_shows_zero_when_no_open_trades(self, app_empty: TestClient) -> None:
        # REQ-WEB-7 empty path: no open trades → sum is 0 → "0.00" (no
        # sign, per spec — the empty-state value is plain "0.00").
        response = app_empty.get("/api/panel/pnl-open")

        assert response.status_code == 200
        assert "0.00" in response.text


# ---------------------------------------------------------------------------
# REQ-WEB-8: pnl-historical card — signed SUM(pnl) closed trades
# ---------------------------------------------------------------------------


class TestPnlHistoricalPanel:
    def test_sums_signed_realized_pnl(self, app_pnl_historical_populated: TestClient) -> None:
        # REQ-WEB-8 happy path: 2 closed trades with pnl 1.50 and -0.25
        # → signed sum = +1.25. The "+" prefix is mandatory per spec.
        response = app_pnl_historical_populated.get("/api/panel/pnl-historical")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "+1.25" in response.text

    def test_shows_zero_when_no_closed_trades(self, app_empty: TestClient) -> None:
        # REQ-WEB-8 empty path: no closed trades → "0.00" (no sign).
        response = app_empty.get("/api/panel/pnl-historical")

        assert response.status_code == 200
        assert "0.00" in response.text


# ---------------------------------------------------------------------------
# format_signed pure-function tests (used by all 3 aggregate routes)
# ---------------------------------------------------------------------------


class TestFormatSigned:
    """Unit tests for the format_signed helper extracted for T3.2.

    The helper is a pure function so we exercise all sign/mode combinations
    directly — no DB, no TestClient, no fixtures. Triangulation: positive,
    negative, zero, plus the unsigned mode used by money-in-open.
    """

    def test_positive_value_gets_plus_prefix(self) -> None:
        # Signed mode (default) — positive values carry a leading "+".
        assert format_signed(Decimal("1.234")) == "+1.23"

    def test_negative_value_gets_minus_prefix(self) -> None:
        # Signed mode (default) — negative values carry a leading "-".
        assert format_signed(Decimal("-0.5")) == "-0.50"

    def test_zero_value_has_no_sign(self) -> None:
        # Per spec, "0.00 when no trades" must NOT show a "+" — zero is
        # rendered without any sign, regardless of the mode.
        assert format_signed(Decimal("0")) == "0.00"

    def test_unsigned_mode_drops_positive_sign(self) -> None:
        # Money-in-open uses unsigned mode — positive values render
        # without the "+" prefix, matching the spec scenario that
        # expects "3.50" (not "+3.50").
        assert format_signed(Decimal("1.23"), signed=False) == "1.23"

    def test_unsigned_mode_keeps_negative_sign(self) -> None:
        # Defense-in-depth: even in unsigned mode, a negative value must
        # still show the "-" so the user can read losses correctly. This
        # is a regression guard — the helper must not silently flip sign.
        assert format_signed(Decimal("-1.00"), signed=False) == "-1.00"
