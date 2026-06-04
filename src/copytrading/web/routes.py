"""HTTP routes for the dashboard.

Layout (one :class:`APIRouter`, 8 endpoints) follows design.md §Routes. All
mutating methods (POST/PUT/PATCH/DELETE) are rejected by FastAPI itself
because only GET handlers are registered — REQ-WEB-14.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import cast

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from copytrading.models import AccountSnapshot
from copytrading.web.app import StoreDep

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
    open_trades = store.get_open_paper_trades()
    all_trades = store.get_all_paper_trades()
    wallets = store.get_all_wallets()
    return cast(
        HTMLResponse,
        request.app.state.templates.TemplateResponse(
            request,
            "index.html",
            {
                "snapshots": snapshots,
                "open_trades": open_trades,
                "all_trades": all_trades,
                "wallets": wallets,
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
# Slice 3 panel stubs — return empty-state HTML so the 7 polling hooks in
# index.html do not 404 in the browser. Slice 3 replaces these bodies with
# the real SUM(CAST(... AS REAL)) aggregates (T3.1..T3.3).
# ---------------------------------------------------------------------------


def _stub_panel(request: Request) -> HTMLResponse:
    return HTMLResponse('<div class="empty-state">No data yet</div>')


@router.get("/api/panel/money-in-open", response_class=HTMLResponse)
def panel_money_in_open(request: Request) -> HTMLResponse:
    """Slice 3 stub — see T3.1..T3.3."""
    return _stub_panel(request)


@router.get("/api/panel/pnl-open", response_class=HTMLResponse)
def panel_pnl_open(request: Request) -> HTMLResponse:
    """Slice 3 stub — see T3.1..T3.3."""
    return _stub_panel(request)


@router.get("/api/panel/pnl-historical", response_class=HTMLResponse)
def panel_pnl_historical(request: Request) -> HTMLResponse:
    """Slice 3 stub — see T3.1..T3.3."""
    return _stub_panel(request)


__all__ = ["router"]
