# Design: web-dashboard

## Context

Adds a read-only `localhost:8000` web panel that observes the live SQLite
database over 7 panels, polled every 5s via HTMX. The bot stays untouched;
the web layer is a pure observer over the existing `Store`. FastAPI +
Jinja2 + HTMX + Chart.js (vendored). No DB writes, no auth, no mobile, no
WebSockets. Total estimate: **~750 LoC** (18 new files, 4 modified).

## Goals / Non-Goals

**Goals**: 7 panels with 5s HTMX polling, 500-row history cap, Decimal
end-to-end, dark/neon UI, local-only bind, strict TDD over 33 scenarios.

**Non-goals**: mobile/responsive <1024px, WebSockets/SSE, auth, mutating
endpoints, CSV/JSON export, replacing Sheets as source of truth.

## Architecture Overview

```
 Browser (HTMX every 5s)
   │  GET /api/panel/<name>
   ▼
 FastAPI route ──► get_store() dep ──► Store(":memory:") / Store(db_path)
                                              │
                                              ▼
                                       SQLite (WAL, read-only per request)
                                              │
                                              ▼
 Jinja2 template (panel partial)  ──►  HTML fragment  ──►  hx-swap="outerHTML"
                                              │
                       (equity-curve only)   ▼
                       data island  ──►  dashboard.js  ──►  Chart.js (vendored)
```

The web layer is a sibling to `cronjobs/` — it imports `Store` and
`models`, never the other way around. Cronjobs keep writing; web just
reads.

## Architecture Decisions

| # | Decision | Choice | Alternative | Tradeoff | Rationale |
|---|----------|--------|-------------|----------|-----------|
| 1 | Routes layout | Single `routes.py` (1 `APIRouter`, 8 endpoints) | Per-panel modules | Splits read surface, but explodes 7 modules for ~70 LoC | One router is scannable; refactor to per-panel when >20 routes. |
| 2 | Equity curve data | HTML data island inside the panel partial | Separate `GET /api/equity-curve-data` JSON endpoint | Two requests per poll cycle, more state to manage | Spec is source of truth; data island matches HTMX's "HTML-fragment" model and halves network round trips. |
| 3 | Decimal serialization | Route builds `list[str]` from Decimals; template `tojson`s the strings | Custom Jinja filter for Decimal | One extra conversion step | `tojson` is stdlib; stringifying in Python keeps the template dumb. `encoders.py` stays as canonical home for any future JSON endpoint. |
| 4 | Store per request | `create_app(db_path)` factory; FastAPI generator dep opens `Store` per request and closes on exit | Module-level singleton | Singleton = connection leaks under reload | Mirrors the existing context-manager pattern; per-request open/close is cheap with WAL. |
| 5 | Bind to 127.0.0.1 | `__main__.py` calls `uvicorn.run(..., host="127.0.0.1", port=8000)` explicitly | Document host in README only | Doc-only = unverifiable | Explicit `host=` is testable via `mock.patch(uvicorn.run)`. |
| 6 | HTMX + Chart.js delivery | Vendored `.min.js` under `static/vendor/` with `NOTICE` for MIT attribution | CDN at runtime | Offline-hostile, license risk | Spec forbids CDN; vendoring is the only compliant option. |
| 7 | Chart re-render | One global `htmx:afterSwap` listener in `dashboard.js` reads `#equity-data` JSON island and calls `chart.update()` | Per-panel inline scripts | Inline scripts = harder to test, harder to cache | Single listener = one render path; Chart.js instance held in module scope. |

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/copytrading/web/__init__.py` | Create | Exports `app = create_app()` and `create_app`. |
| `src/copytrading/web/__main__.py` | Create | `uvicorn.run("copytrading.web:app", host="127.0.0.1", port=8000)`. |
| `src/copytrading/web/app.py` | Create | `create_app(db_path)` factory; mounts router, static dir, Jinja2. |
| `src/copytrading/web/routes.py` | Create | 1 index + 7 panel routes; uses `get_store` dep. |
| `src/copytrading/web/encoders.py` | Create | `DecimalEncoder` (json.JSONEncoder subclass) — kept for reuse, tested independently. |
| `src/copytrading/web/templates/base.html` | Create | HTML5 shell, links CSS, loads htmx + dashboard.js. |
| `src/copytrading/web/templates/index.html` | Create | 7 panel placeholders, each with `hx-get` + `hx-trigger="every 5s"`. |
| `src/copytrading/web/templates/panels/{equity_curve,open_positions,trade_history,wallets,money_in_open,pnl_open,pnl_historical}.html` | Create | One partial per panel; empty-state copy via shared `partials/empty_state.html`. |
| `src/copytrading/web/templates/partials/empty_state.html` | Create | Reusable empty-state block. |
| `src/copytrading/web/static/css/dashboard.css` | Create | `:root` custom properties (cyan/violet/dark), monospace `.number`, `backdrop-filter: blur()` on panels. |
| `src/copytrading/web/static/js/dashboard.js` | Create | `htmx:afterSwap` listener → Chart.js init/update. |
| `src/copytrading/web/static/vendor/{htmx.min.js,chart.umd.min.js}` | Create | Vendored binaries. |
| `src/copytrading/web/static/vendor/NOTICE` | Create | MIT attribution for HTMX + Chart.js. |
| `src/copytrading/store.py` | Modify | + `get_all_snapshots() -> list[AccountSnapshot]`, + `get_all_paper_trades(limit: int = 500) -> list[PaperTrade]`. |
| `tests/unit/test_store.py` | Modify | + 8 scenarios for the 2 new methods. |
| `tests/unit/test_web.py` | Create | 17 scenarios: route HTML markers, static serving, bind assertion, 405 on POST. |
| `tests/unit/test_web_decimal_encoder.py` | Create | Encoder serializes Decimal as string. |
| `pyproject.toml` | Modify | + `fastapi>=0.115`, `uvicorn[standard]>=0.32`, `jinja2>=3.1`. |
| `README.md` | Modify | "Run the dashboard" section: `uv run python -m copytrading.web`. |

## Data Layer (new `Store` methods)

```python
def get_all_snapshots(self) -> list[AccountSnapshot]:
    """ASC by snapshot_at. Empty list (not None) when table empty."""
    rows = self.conn.execute(
        "SELECT id, equity, open_trades, total_pnl, snapshot_at "
        "FROM account_snapshots ORDER BY snapshot_at ASC"
    ).fetchall()
    return [AccountSnapshot(...) for r in rows]  # Decimal(str(r[1])) etc.

def get_all_paper_trades(self, limit: int = 500) -> list[PaperTrade]:
    """DESC by opened_at. LIMIT enforced at SQL."""
    rows = self.conn.execute(
        "SELECT id, copied_from_wallet, ..., opposite_asset "
        "FROM paper_trades ORDER BY opened_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [PaperTrade(...) for r in rows]
```

The 3 aggregate cards (money-in-open, pnl-open, pnl-historical) use
inline SQL in route handlers — `SUM(CAST(... AS REAL))` per spec wording
(spec literally writes the SQL, so we mirror it verbatim). Decimals
are recovered with `Decimal(str(row[0]))` to avoid float→Decimal
back-conversion drift.

## Route Design

| Method | Path | Response | Notes |
|--------|------|----------|-------|
| GET | `/` | `text/html` (full page) | Renders `index.html`; 7 panel placeholders. |
| GET | `/api/panel/equity-curve` | HTML partial | `<canvas>` + `<script type="application/json" id="equity-data">` island. |
| GET | `/api/panel/open-positions` | HTML `<table>` partial | DESC by `opened_at`; cols: title, side, current_value, percent_pnl, opened_at. |
| GET | `/api/panel/trade-history` | HTML `<table>` partial | `limit=500` enforced; cols: opened_at, title, side, entry, exit, pnl, status. |
| GET | `/api/panel/wallets` | HTML table partial | ASC by `rank`; cols: rank, username (or truncated addr), total_pnl, last_checked_at. |
| GET | `/api/panel/money-in-open` | HTML card partial | `SUM(current_value)` of open trades → "0.00" when empty. |
| GET | `/api/panel/pnl-open` | HTML card partial | `SUM(current_value − initial_value)` of open trades → signed. |
| GET | `/api/panel/pnl-historical` | HTML card partial | `SUM(pnl)` of closed trades → signed. |

## HTMX Polling Strategy

Every panel placeholder in `index.html` is a `<div id="panel-X" hx-get="/api/panel/X" hx-trigger="every 5s" hx-swap="outerHTML">`. The initial response from `GET /` contains the **first** panel HTML inside each div (server-side rendered), so the page is useful before the first tick fires. Subsequent ticks replace the div's contents with the latest partial — no full reload, no flicker (CSS reserves card heights).

## Chart.js Integration

- `chart.umd.min.js` loaded once at end of `base.html`.
- `dashboard.js` registers one global listener:
  ```js
  document.body.addEventListener('htmx:afterSwap', (e) => {
    const data = e.target.querySelector('#equity-data');
    if (data) renderEquityChart(JSON.parse(data.textContent));
  });
  ```
- `renderEquityChart` holds a module-scoped `Chart` instance, calls
  `chart.update()` on subsequent swaps (no destroy/recreate — preserves
  animation state and avoids a flash).

## Styling

`dashboard.css` structure:

- `:root` custom properties: `--neon-cyan: #0ff`, `--neon-violet: #8b5cf6`,
  `--bg-base: #0a0a0f`, `--bg-panel: rgba(20,20,30,0.6)`.
- `.theme-dark` body class set in `base.html`.
- `.panel { backdrop-filter: blur(12px); }` for glassmorphism.
- `.number { font-family: "JetBrains Mono", "Fira Code", monospace; }`.
- `transition: color 200ms, background 200ms` on `.number` so a tick
  that changes a value visibly flashes (no `@keyframes` — only value-
  triggered transitions).

## Testing Strategy

| Layer | What | How |
|-------|------|-----|
| Unit (Store) | 2 new methods (8 scenarios) | `:memory:` Store, seed via existing helpers. |
| Unit (Encoder) | Decimal → string in JSON | `json.dumps(..., cls=DecimalEncoder)`. |
| Integration (Routes) | 7 panel GETs return 200 with expected markers | `TestClient(create_app(db_path=tmp_path/"t.db"))`; seed via `Store`; assert HTML substrings. |
| Integration (Static + bind + read-only) | Vendor file served; CSS markers; no CDN hosts in `/`; `every 5s` ≥ 7×; `POST /` → 405; `__main__.main` called with `host="127.0.0.1"`. | `TestClient` + `mock.patch(uvicorn.run)`. |
| Visual (manual) | Dark mode + Chart.js plot | `uv run python -m copytrading.web`, browser screenshot. |

All 33 spec scenarios are pytest-executable; no JS test framework needed.

## Sequence Diagram (one polling tick)

```
Browser                       FastAPI                  Store          SQLite
   │                              │                       │              │
   │  GET /api/panel/open-pos     │                       │              │
   │─────────────────────────────►│                       │              │
   │                              │  get_store() yields   │              │
   │                              │──────────────────────►│              │
   │                              │                       │  SELECT ...  │
   │                              │                       │─────────────►│
   │                              │                       │◄─────────────│
   │                              │                       │  rows        │
   │                              │◄──────────────────────│              │
   │                              │  TemplateResponse     │              │
   │                              │  (Jinja2 renders)     │              │
   │  200 HTML fragment           │                       │              │
   │◄─────────────────────────────│                       │              │
   │  hx-swap="outerHTML"         │                       │              │
   │  (no full reload)            │                       │              │
```

For the equity-curve panel the response additionally contains the
`#equity-data` island, and `htmx:afterSwap` triggers
`renderEquityChart()` in the browser.

## Open Questions / Risks

- **License attribution**: vendoring Chart.js (MIT) + HTMX (BSD-2) needs
  a `NOTICE` file — small task, owner TBD.
- **Empty-state copy**: per spec wording is illustrative ("No data yet —
  waiting for first snapshot"); final wording deferred to `sdd-apply`.
- **Layout shift on tick**: mitigated by `min-height` on `.panel`; if
  tick still flickers we'll add `contain: layout` in a follow-up.
- **Concurrent reads vs cron writes**: WAL allows concurrent reads; we
  open a fresh connection per request so no stale-connection risk.
- **Chart.js size on every page load**: ~70KB minified is acceptable
  for desktop localhost; out of scope to lazy-load.
- **Core-infrastructure coordination**: storage delta does not conflict
  (verified in spec phase — `core-infrastructure` declares
  REQ-STORAGE-1..6 only). If `core-infrastructure` adds the same methods
  before this lands, we drop our copies during merge.

## Next Step

Ready for `sdd-tasks`. Forecast: **3 chained PR slices** (store reads
→ dashboard shell + 4 panels → 3 aggregate cards + README), each well
under the 400-line review budget.
