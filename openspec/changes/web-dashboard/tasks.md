# Tasks: web-dashboard

## Review Workload Forecast

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Low

- Estimated changed lines: ~750 (18 new, 4 modified). Per-slice: ~80 / ~350 / ~200 — Low risk each.

All 33 spec scenarios (8 storage + 25 web-dashboard) mapped below.

## Slice 1: Store reads + tests (PR 1)

- [ ] **T1.1** [test-first] In `tests/unit/test_store.py` add 3 tests for `Store.get_all_snapshots()`: ASC order, empty→`[]`, Decimal round-trip. Covers storage delta (3/3).
- [ ] **T1.2** [code] Add `get_all_snapshots() -> list[AccountSnapshot]` to `src/copytrading/store.py` (SELECT ... ORDER BY snapshot_at ASC; `Decimal(str(row[n]))`). Depends: T1.1.
- [ ] **T1.3** [test-first] Add 5 tests for `Store.get_all_paper_trades(limit)`: cap=500, DESC, smaller limit, empty→`[]`, LIMIT at SQL. Covers storage delta (5/5).
- [ ] **T1.4** [code] Add `get_all_paper_trades(limit: int = 500) -> list[PaperTrade]` with `LIMIT ?` at SQL. Depends: T1.3.
- [ ] **T1.5** [verify] `uv run pytest tests/unit/test_store.py -v` → 8/8 new pass; mypy+ruff clean. **Rollback**: 2 additive methods + 8 tests; cronjobs unaffected.

## Slice 2: Dashboard shell + 4 panels + vendor (PR 2)

- [ ] **T2.1** [config] Add `fastapi>=0.115`, `uvicorn[standard]>=0.32`, `jinja2>=3.1` to `pyproject.toml`; `uv sync`.
- [ ] **T2.2** [test-first] Create `tests/unit/test_web_decimal_encoder.py` (2 cases: Decimal→str, list[Decimal]→list[str]).
- [ ] **T2.3** [code] Create `web/{__init__.py,encoders.py}` (`DecimalEncoder.default()` → `str(o)`). Depends: T2.2.
- [ ] **T2.4** [test-first] In `tests/unit/test_web.py` add 4 panel tests + 4 empty-state cases. Covers REQ-WEB-1..5,11.
- [ ] **T2.5** [code] Create `web/app.py` (`create_app(db_path)`, `get_store` dep, static mount, Jinja2Templates), `web/routes.py` (1 index + 4 panel routes), `templates/{base,index}.html`, 4 panel partials, `partials/empty_state.html`, minimal `static/css/dashboard.css`. Depends: T2.4.
- [ ] **T2.6** [test-first] Add 5 tests: vendor served, `every 5s` marker, no-CDN-hosts, POST→405, CSS markers. Covers REQ-WEB-9,10,12,14.
- [ ] **T2.7** [config] Vendor `htmx.min.js` + `chart.umd.min.js` (4.x) into `web/static/vendor/`; add `NOTICE` (MIT+BSD-2). Depends: T2.5.
- [ ] **T2.8** [code] Create `web/__main__.py` calling `uvicorn.run(..., host="127.0.0.1", port=8000)`; test asserts bind arg via `mock.patch(uvicorn.run)`. Covers REQ-WEB-13. Depends: T2.6.
- [ ] **T2.9** [code] Finalize `static/css/dashboard.css` (`:root` cyan/violet vars, `.theme-dark`, `.number` monospace, `backdrop-filter`). Create `static/js/dashboard.js` (`htmx:afterSwap` → `renderEquityChart` via `#equity-data` island). Depends: T2.7.
- [ ] **T2.10** [verify] `uv run pytest tests/unit/test_web.py tests/unit/test_web_decimal_encoder.py -v` → all pass; mypy+ruff clean. **Rollback**: reverts `web/` except `encoders.py`; Slice 1 unaffected.

## Slice 3: 3 aggregate cards + README (PR 3)

- [ ] **T3.1** [test-first] Add 6 tests in `test_web.py`: money-in-open (sum, 0.00), pnl-open (signed, 0.00), pnl-historical (signed, 0.00). Covers REQ-WEB-6,7,8.
- [ ] **T3.2** [code] Add 3 panel routes in `web/routes.py`; use `SUM(CAST(... AS REAL))` per spec; recover via `Decimal(str(row[0]))`; format signed 2-decimal. Depends: T3.1.
- [ ] **T3.3** [code] Create 3 panel partials in `web/templates/panels/`; add HTMX placeholders to `index.html`. Depends: T3.2.
- [ ] **T3.4** [docs] Add "Run the dashboard" section to `README.md`: `uv run python -m copytrading.web` (127.0.0.1:8000, no auth, v1).
- [ ] **T3.5** [verify] Full gate: `uv run pytest`, `mypy src tests`, `ruff check .`, `ruff format --check .` → all 0. Mark proposal success criteria ✅. **Rollback**: 3 routes + 3 partials + README; Slice 2 still serves 4 panels.

Slice order `1 → 2 → 3`, each merges to `main`. Reverts safe (additive only).
