"""HTTP routes for the dashboard.

Layout (one :class:`APIRouter`, 9 endpoints) follows design.md §Routes. All
mutating methods (POST/PUT/PATCH/DELETE) are rejected by FastAPI itself
because only GET handlers are registered — REQ-WEB-14.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from decimal import Decimal
from typing import cast

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from copytrading.models import AccountSnapshot
from copytrading.store import Store
from copytrading.web.app import StoreDep
from copytrading.web.formatting import format_signed

router = APIRouter()


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
def index(request: Request, store: StoreDep) -> HTMLResponse:
    """Render the full dashboard with 7 panel placeholders.

    The initial response contains the server-rendered HTML for every panel
    so the page is useful before the first 5s tick fires. The placeholders
    carry ``hx-get`` + ``hx-trigger="every 5s"`` so HTMX will refresh them
    every 5 seconds.
    """
    snapshots = store.get_all_snapshots()
    latest_equity = snapshots[-1].equity if snapshots else Decimal("0")
    open_trades = store.get_open_paper_trades()
    all_trades = store.get_all_paper_trades()
    wallets = store.get_all_wallets()
    money_in_open = format_signed(_sum_open_current_value(store), signed=False)
    pnl_open = format_signed(_sum_open_unrealized(store))
    pnl_historical = format_signed(_sum_closed_pnl(store))
    # Daily gain: difference between last and first snapshot equity today
    daily_gain = latest_equity - snapshots[0].equity if len(snapshots) >= 2 else Decimal("0")
    return cast(
        HTMLResponse,
        request.app.state.templates.TemplateResponse(
            request,
            "index.html",
            {
                "snapshots": snapshots,
                "latest_equity": latest_equity,
                "daily_gain": daily_gain,
                "open_trades": open_trades,
                "all_trades": all_trades,
                "wallets": wallets,
                "money_in_open": money_in_open,
                "pnl_open": pnl_open,
                "pnl_historical": pnl_historical,
            },
        ),
    )


# ---------------------------------------------------------------------------
# Panel endpoints
# ---------------------------------------------------------------------------


def _equities_json(snapshots: Sequence[AccountSnapshot]) -> str:
    """Build the equity-curve data island. Pure function — easy to test."""
    return json.dumps([str(s.equity) for s in snapshots])


@router.get("/api/panel/equity-curve", response_class=HTMLResponse)
def panel_equity_curve(request: Request, store: StoreDep) -> HTMLResponse:
    """Equity-curve panel: <canvas> + <script id='equity-data'> island."""
    snapshots = store.get_all_snapshots()
    return cast(
        HTMLResponse,
        request.app.state.templates.TemplateResponse(
            request,
            "panels/equity_curve.html",
            {"snapshots": snapshots, "equities_json": _equities_json(snapshots)},
        ),
    )


@router.get("/api/panel/open-positions", response_class=HTMLResponse)
def panel_open_positions(request: Request, store: StoreDep) -> HTMLResponse:
    """Open positions: one <tr> per paper_trade WHERE status='open'."""
    open_trades = store.get_open_paper_trades()
    return cast(
        HTMLResponse,
        request.app.state.templates.TemplateResponse(
            request,
            "panels/open_positions.html",
            {"open_trades": open_trades},
        ),
    )


@router.get("/api/panel/trade-history", response_class=HTMLResponse)
def panel_trade_history(request: Request, store: StoreDep) -> HTMLResponse:
    """Trade history: most recent 500 paper_trades DESC by opened_at."""
    all_trades = store.get_all_paper_trades(limit=500)
    return cast(
        HTMLResponse,
        request.app.state.templates.TemplateResponse(
            request,
            "panels/trade_history.html",
            {"all_trades": all_trades},
        ),
    )


@router.get("/api/panel/wallets", response_class=HTMLResponse)
def panel_wallets(request: Request, store: StoreDep) -> HTMLResponse:
    """Tracked wallets: one <tr> per wallet, ordered ASC by rank."""
    wallets = store.get_all_wallets()
    return cast(
        HTMLResponse,
        request.app.state.templates.TemplateResponse(
            request,
            "panels/wallets.html",
            {"wallets": wallets},
        ),
    )


# ---------------------------------------------------------------------------
# Slice 3 aggregate cards (REQ-WEB-6, REQ-WEB-7, REQ-WEB-8)
#
# The spec writes the SQL literally as ``SUM(CAST(... AS REAL))`` and the
# Decimal recovery is mandatory (``Decimal(str(row[0]))``) to avoid the
# float→Decimal back-conversion drift that bites us if we go through
# ``Decimal(float)``. The 3 helpers below keep the SQL colocated with the
# formatting layer so the index page and the per-panel route share the
# exact same numbers.
# ---------------------------------------------------------------------------


def _sum_open_current_value(store: Store) -> Decimal:
    """REQ-WEB-6: ``SUM(CAST(current_value AS REAL))`` over open trades."""
    row = store.conn.execute(
        "SELECT SUM(CAST(current_value AS REAL)) FROM paper_trades WHERE status = 'open'"
    ).fetchone()
    return Decimal(str(row[0])) if row and row[0] is not None else Decimal("0")


def _sum_open_unrealized(store: Store) -> Decimal:
    """REQ-WEB-7: ``SUM(CAST(current_value AS REAL)) - SUM(CAST(initial_value AS REAL))`` open."""
    row = store.conn.execute(
        "SELECT SUM(CAST(current_value AS REAL)) - SUM(CAST(initial_value AS REAL)) "
        "FROM paper_trades WHERE status = 'open'"
    ).fetchone()
    return Decimal(str(row[0])) if row and row[0] is not None else Decimal("0")


def _sum_closed_pnl(store: Store) -> Decimal:
    """REQ-WEB-8: ``SUM(CAST(pnl AS REAL))`` over closed trades."""
    row = store.conn.execute(
        "SELECT SUM(CAST(pnl AS REAL)) FROM paper_trades WHERE status = 'closed'"
    ).fetchone()
    return Decimal(str(row[0])) if row and row[0] is not None else Decimal("0")


@router.get("/api/panel/money-in-open", response_class=HTMLResponse)
def panel_money_in_open(request: Request, store: StoreDep) -> HTMLResponse:
    """Money-in-open card (REQ-WEB-6).

    Renders ``SUM(CAST(current_value AS REAL))`` of all open trades as
    a USDC string with 2 decimals. Zero is rendered as ``"0.00"`` (the
    spec wording, not a positive ``"+"`` prefix).
    """
    total = format_signed(_sum_open_current_value(store), signed=False)
    return cast(
        HTMLResponse,
        request.app.state.templates.TemplateResponse(
            request,
            "panels/money_in_open.html",
            {"total": total},
        ),
    )


@router.get("/api/panel/pnl-open", response_class=HTMLResponse)
def panel_pnl_open(request: Request, store: StoreDep) -> HTMLResponse:
    """P&L of open positions (REQ-WEB-7).

    Signed 2-decimal USDC string for the unrealized PnL across all open
    trades (``current_value - initial_value`` summed). Zero renders as
    ``"0.00"`` (no sign), positive as ``"+N.NN"``, negative as ``"-N.NN"``.
    """
    total = format_signed(_sum_open_unrealized(store))
    return cast(
        HTMLResponse,
        request.app.state.templates.TemplateResponse(
            request,
            "panels/pnl_open.html",
            {"total": total},
        ),
    )


@router.get("/api/panel/pnl-historical", response_class=HTMLResponse)
def panel_pnl_historical(request: Request, store: StoreDep) -> HTMLResponse:
    """Historical P&L (REQ-WEB-8).

    Signed 2-decimal USDC string summing the ``pnl`` column of all closed
    trades. Same sign convention as :func:`panel_pnl_open`.
    """
    total = format_signed(_sum_closed_pnl(store))
    return cast(
        HTMLResponse,
        request.app.state.templates.TemplateResponse(
            request,
            "panels/pnl_historical.html",
            {"total": total},
        ),
    )


@router.get("/api/panel/kpi-equity", response_class=HTMLResponse)
def panel_kpi_equity(request: Request, store: StoreDep) -> HTMLResponse:
    """Equity KPI card: latest snapshot value + daily gain."""
    snapshots = store.get_all_snapshots()
    latest_equity = snapshots[-1].equity if snapshots else Decimal("0")
    daily_gain = latest_equity - snapshots[0].equity if len(snapshots) >= 2 else Decimal("0")
    return cast(
        HTMLResponse,
        request.app.state.templates.TemplateResponse(
            request,
            "panels/kpi_equity.html",
            {
                "latest_equity": latest_equity,
                "daily_gain": daily_gain,
            },
        ),
    )


__all__ = ["router"]
