# Proposal: web-dashboard

## Intent

The copytrading bot is operational but state is only inspectable via `sqlite3 copytrading.db` and Google Sheets. The operator needs a **real-time, ultra-futuristic web panel** on `localhost:8000` showing **7 read-only views** of the live SQLite, polled every **5 seconds** (cron cadence ≤ 1 min). No DB writes, no auth, no trading logic — pure observer over the existing `Store`.

## Scope

### In Scope

1. New module `src/copytrading/web/` — FastAPI app, Jinja2 templates, static assets, routes.
2. `GET /` renders 7 panels; per-panel HTMX partials poll `/api/panel/*` every 5s.
3. Two new read-only `Store` methods: `get_all_snapshots()` and `get_all_paper_trades(limit=500)`.
4. New deps: `fastapi`, `uvicorn[standard]`, `jinja2`. Chart.js 4.x vendored locally.
5. Tests via `fastapi.testclient.TestClient` + pytest. **Strict TDD applies.**

### Out of Scope

WebSockets / SSE. Auth. Mutating endpoints. Mobile-first responsive (desktop-first, degrade gracefully). CSV/JSON export. Replacing Sheets as source of truth.

## Capabilities

> `core-infrastructure` is still active (not archived); its specs are live for this proposal.

### New

- `web-dashboard`: FastAPI + Jinja2/HTMX server-rendered panel, 7 read-only views, 5s polling.

### Modified

- `storage` (delta): adds `get_all_snapshots()` and `get_all_paper_trades(limit=500)`. `paper-trading` unchanged.

## Approach

- **Stack**: FastAPI + Jinja2 + HTMX + Chart.js 4.x local at `static/vendor/chart.umd.min.js` (no CDN, offline-friendly). No Node, no build step.
- **Polling**: HTMX polls every 5s; routes return full HTML fragments (no JSON-only endpoints).
- **History cap**: trade history shows the most recent **500** paper trades (`DESC BY opened_at`). `Store.get_all_paper_trades(limit=500)` enforces it server-side.
- **Visual**: dark + neon palette (cyan/violet), monospace numbers, moderate glassmorphism via `backdrop-filter` only. Animations only on value change — flash the figure when a number ticks, never decorate.
- **`Decimal` end-to-end**; never `float` in the web layer. `Store` opened read-only per request via FastAPI dependency; WAL allows concurrent reads with cronjobs.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/copytrading/web/{__init__,app,routes}.py` | New | FastAPI app + 7 panel routes. |
| `src/copytrading/web/templates/` | New | `base.html`, `index.html`, 7 partials. |
| `src/copytrading/web/static/` | New | css, js, vendor (Chart.js local). |
| `src/copytrading/store.py` | Modified | + `get_all_snapshots()`, + `get_all_paper_trades(limit=500)`. |
| `pyproject.toml` | Modified | + `fastapi`, `uvicorn[standard]`, `jinja2`. |
| `tests/unit/test_web.py` | New | Route tests via `TestClient`. |
| `tests/unit/test_store.py` | Modified | Tests for 2 new read methods. |
| `README.md` | Modified | `uvicorn` section. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `Decimal` not JSON/HTTP-serializable | High | Custom `JSONResponse` encoder or `str(d)` per route. |
| Layout shift on each 5s tick | Med | Reserved card heights; only numeric content swaps. |
| Long history bloats response | Low | Server-side cap at 500. |
| Concurrent SQLite read vs cron write | Low | WAL mode; read-only connection per request. |

## PR Split

Estimated **700–800 LoC total** — over the 400-line review budget. Recommend 3-slice chained PR: **(1) store reads** — 2 new `Store` methods + tests (~80 LoC); **(2) dashboard shell + first 4 panels** — FastAPI app, base template, equity/open/history/wallets (~350 LoC); **(3) aggregate panels** — money-in-open, PnL-of-open, historical PnL, README (~200 LoC). Final chain decision deferred to `sdd-tasks`.

## Rollback Plan

No live state, no DB writes, no auth. `git revert <slice>` (×3) or single revert. `Store` extra methods are additive — backward compatible.

## Dependencies

- `core-infrastructure` (active) — provides `Store` and `paper_trades` schema.
- New: `fastapi>=0.115`, `uvicorn[standard]>=0.32`, `jinja2>=3.1`.
- Vendored: Chart.js 4.x (MIT, local).
- `bootstrap-tooling` (archived) — pytest/mypy/ruff already wired.

## Success Criteria

- [ ] `uv run uvicorn copytrading.web:app --reload` serves on `localhost:8000`.
- [ ] `GET /` renders all 7 panels with HTMX hooks.
- [ ] All 7 panels auto-refresh every **5 seconds** without full page reload.
- [ ] Equity curve plots real `account_snapshots` (or empty-state placeholder).
- [ ] Open positions = `paper_trades WHERE status='open'`.
- [ ] Trade history = last **500 trades**, `DESC BY opened_at`.
- [ ] Aggregates match SQL ground truth within ±0.01 USDC.
- [ ] `uv run pytest`, `mypy src tests`, `ruff check .`, `ruff format --check .` all exit 0.

## Open Questions

- **Auth**: confirm local-only is fine (no basic-auth prompt).
- **Mobile**: graceful degradation only, or full responsive?
- **Empty-state copy**: wording when DB has no snapshots/trades yet.
- **Decimal JSON**: custom encoder vs `str(d)` per route — spec will pin one.

## Next Phase

`sdd-spec` — `openspec/changes/web-dashboard/specs/web-dashboard/spec.md` (new) + `specs/storage/spec.md` (delta for 2 new read methods). Given/When/Then per panel; RFC 2119 keywords per `config.yaml → rules.specs`.

## Cronjob / risk interaction

**No cronjob changes. No risk-cap math touched. Read-only over the existing DB.** 0.5% / 200 USDC policy unaffected.
