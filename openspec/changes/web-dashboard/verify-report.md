# Verify Report — web-dashboard

**Change**: web-dashboard
**Project**: copytrading
**Mode**: Strict TDD
**Test runner**: `uv run pytest`
**Branch**: master (pushed to origin/master, working tree clean)
**Verification date**: 2026-06-08 (re-verified after WARNING fixes)
**Persistence**: hybrid (this file + Engram `sdd/web-dashboard/verify-report`)

## Re-verification (2026-06-08)

After 9 commits addressing the previous PASS WITH WARNINGS verdict, all issues are resolved:

| Issue | Previous | Now |
|-------|----------|-----|
| SQLite thread bug (showstopper) | N/A (discovered) | ✅ `check_same_thread=False` |
| `format_signed` undocumented | ⚠️ WARNING | ✅ Design Decision #8 |
| `__main__.py` hardcodes `db_path` | ⚠️ WARNING | ✅ `_resolve_db_path()` + `COPYTRADING_DB_PATH` |
| `wallets.username` schema mismatch | ⚠️ WARNING | ✅ Column added to schema + upsert + select |
| REQ-WEB-12 `<link>` not asserted | ⚠️ PARTIAL | ✅ `test_index_links_to_local_stylesheet` |

## Build / Tests / Coverage Evidence

- **pytest**: 145 passed (was 143), 0 failed, 1 warning (httpx deprecation — external). Exit code 0.
- **mypy** (`uv run mypy src tests`): Success: no issues found in 32 source files.
- **ruff check** (`uv run ruff check .`): All checks passed.
- **ruff format --check** (`uv run ruff format --check .`): 33 files already formatted (was 32).
- **Tasks**: 20/20 [x], 0 [ ] — all complete.
- **Design**: format_signed documented as Decision #8.
- **Schema**: wallets.username column present and round-tripping in tests.
- **DB path**: `_resolve_db_path()` reads `COPYTRADING_DB_PATH` env, no longer requires Google Sheets vars.
- **Store**: `check_same_thread=False` for FastAPI async dependency generator.
- **coverage** (changed files only, with `pytest-cov 7.1.0`):

| File | Stmts | Miss | Cover | Missing lines |
|------|-------|------|-------|---------------|
| `src/copytrading/web/__init__.py` | 2 | 0 | **100%** | — |
| `src/copytrading/web/app.py` | 25 | 0 | **100%** | — |
| `src/copytrading/web/routes.py` | 62 | 0 | **100%** | — |
| `src/copytrading/web/formatting.py` | 9 | 0 | **100%** | — |
| `src/copytrading/web/encoders.py` | 8 | 1 | 88% | L22 (`super().default(o)` fallback) |
| `src/copytrading/web/__main__.py` | 8 | 1 | 88% | L34 (`if __name__ == "__main__"`) |
| `src/copytrading/store.py` (full) | 86 | 8 | 91% | L124, L206, L249-256, L392-395 (pre-existing repo methods, NOT new from this change) |

**Per-scope coverage of the 2 NEW Store methods** (the only store additions in this change):
- `Store.get_all_snapshots()` (L482-497) — 100% covered
- `Store.get_all_paper_trades()` (L397-449) — 100% covered
- The 8 missed lines in store.py are inside pre-existing methods (`Store.conn` property, `prune_wallets_not_in`, `get_market`, `get_realized_pnl`) — not web-dashboard debt.

**Average changed-file coverage**: 95% (200 stmts, 10 missed).

## Task Completeness

| Slice | Tasks | Completed | Status |
|-------|-------|-----------|--------|
| Slice 1: Store reads | 5 | 5/5 | ✅ |
| Slice 2: Dashboard shell + 4 panels + vendor | 10 | 10/10 | ✅ |
| Slice 3: 3 aggregate cards + README | 5 | 5/5 | ✅ |
| **Total** | **20** | **20/20** | **✅** |

All 20 tasks marked `[x]` in `openspec/changes/web-dashboard/tasks.md` (verified by `grep -c "^- \[x\]"` → 20).

## TDD Compliance (Strict TDD Mode)

| Check | Result | Details |
|-------|--------|---------|
| Test-first tags on tasks | ✅ | All 8 test-first tasks (T1.1, T1.3, T2.2, T2.4, T2.6, T3.1, plus 2 in-store) precede their GREEN code |
| RED confirmed (tests exist) | ✅ | 42 new tests across 3 test files |
| GREEN confirmed (tests pass) | ✅ | 52/52 pass in scoped run (test_web.py 27, test_store.py new 8, test_web_decimal_encoder.py 2, plus pre-existing). 143/143 pass in full suite. |
| Triangulation adequate | ✅ | Format helper has 5 cases (sign × mode); each panel has happy + empty; store has ASC + empty + Decimal round-trip + DESC + limit + SQL-level + smaller-limit + empty (8) |
| Safety Net for modified files | ✅ | `tests/unit/test_store.py` was modified (Slice 1). Pre-existing tests still pass (23/23 in test_store.py). |
| TDD Cycle Evidence table | ⚠️ | The strict-tdd-verify.md template expects a per-task RED/GREEN/TRIANGULATE/SAFETY NET/REFACTOR table in apply-progress. The actual apply-progress #162 is a recovery note (the Slice 3 sub-agent returned empty); the TDD evidence is embedded in tasks.md `[test-first]` tags and "Covers" annotations but not in a dedicated table. |
| **TDD Compliance** | **6/7** | The missing evidence table is a process gap, not a code gap — work was done correctly, tests pass, commits landed. |

## Test Layer Distribution

| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit | 18 | `test_web_decimal_encoder.py` (2), `test_store.py` new (8), `TestFormatSigned` in `test_web.py` (5), and pre-existing store tests (3 touched by the change scope) | pytest 9.0.3, `:memory:` SQLite, `TestClient` |
| Integration | 27 | `test_web.py` (TestIndexPage, TestEquityCurvePanel, TestOpenPositionsPanel, TestTradeHistoryPanel, TestWalletsPanel, TestServingAndBind, TestBindAddress, TestMoneyInOpenPanel, TestPnlOpenPanel, TestPnlHistoricalPanel) | `fastapi.testclient.TestClient` + file-backed SQLite + WAL |
| E2E | 0 | n/a | not applicable — visual layer; manual review per design.md |

**Total new tests for this change**: 42 (8 storage + 27 web + 2 encoder + 5 format_signed). Note: some pre-existing tests in test_store.py (`TestStoreLifecycle`, `TestWalletRepo`, `TestPaperTradeRepo` non-`get_all_*` cases) are also exercised, giving 52 in the scoped run.

## Assertion Quality Audit (Step 5f)

I scanned all 3 new/modified test files for trivial assertions. Findings:

- **Tautologies**: None. All `assert` statements compare computed values against expected values.
- **Orphan empty checks**: None. Every empty-state test has a companion populated test (e.g., `test_sums_current_value_of_open_trades` ↔ `test_shows_zero_when_no_open_trades`).
- **Type-only assertions**: None used alone. `assert isinstance(parsed["equity"], str)` is combined with a value assertion (`assert parsed == {"equity": "200.50"}`).
- **Smoke-test-only**: None. `TestIndexPage` asserts both status code AND all 7 panel hook strings.
- **Implementation detail coupling**: None. Tests assert HTTP behavior, not FastAPI internals.
- **Ghost loops**: None — no test asserts inside a loop over a possibly-empty collection.
- **Mocks > 2× assertions**: 1 mock total (`mock.patch.object(web_main.uvicorn, "run")` in `TestBindAddress`) for 1 assertion about the bind. Mock/assertion ratio is 1:1, not mock-heavy.

**Assertion quality**: ✅ All assertions verify real behavior.

## Spec Compliance Matrix (33 scenarios)

### Storage delta — 8/8 PASS

| # | Scenario | Covering test (file::class::method) | Result |
|---|----------|--------------------------------------|--------|
| 1 | REQ-STORAGE-NEW-1: Returns snapshots in chronological order | `test_store.py::TestAccountSnapshotRepo::test_get_all_snapshots_returns_ascending_order` | ✅ COMPLIANT |
| 2 | REQ-STORAGE-NEW-1: Returns empty list when no snapshots exist | `test_store.py::TestAccountSnapshotRepo::test_get_all_snapshots_empty_returns_empty_list` | ✅ COMPLIANT |
| 3 | REQ-STORAGE-NEW-1: Decimals round-trip from TEXT storage | `test_store.py::TestAccountSnapshotRepo::test_get_all_snapshots_decimal_round_trip` | ✅ COMPLIANT |
| 4 | REQ-STORAGE-NEW-2: Caps result at the limit | `test_store.py::TestPaperTradeRepo::test_get_all_paper_trades_caps_at_default_limit` (inserts 600, asserts `len==500`) | ✅ COMPLIANT |
| 5 | REQ-STORAGE-NEW-2: Orders DESC by opened_at | `test_store.py::TestPaperTradeRepo::test_get_all_paper_trades_orders_desc_by_opened_at` | ✅ COMPLIANT |
| 6 | REQ-STORAGE-NEW-2: Honors a smaller limit | `test_store.py::TestPaperTradeRepo::test_get_all_paper_trades_honors_smaller_limit` | ✅ COMPLIANT |
| 7 | REQ-STORAGE-NEW-2: Returns empty list when no trades exist | `test_store.py::TestPaperTradeRepo::test_get_all_paper_trades_empty_returns_empty_list` | ✅ COMPLIANT |
| 8 | REQ-STORAGE-NEW-2: Limit is enforced at SQL level | `test_store.py::TestPaperTradeRepo::test_get_all_paper_trades_limit_at_sql_level` (uses `set_trace_callback` to assert `LIMIT 10` in executed SQL) | ✅ COMPLIANT |

### Web-dashboard capability — 24/25 PASS, 1 PARTIAL

| # | Scenario | Covering test | Result |
|---|----------|----------------|--------|
| 1 | REQ-WEB-1: Index returns 200 with all 7 panels present | `test_web.py::TestIndexPage::test_index_renders_even_with_empty_database` (empty DB) | ✅ COMPLIANT |
| 2 | REQ-WEB-1: Index renders with populated database | `test_web.py::TestIndexPage::test_index_returns_200_with_seven_panels` (populated DB) | ✅ COMPLIANT |
| 3 | REQ-WEB-2: Renders chart data for populated snapshots | `test_web.py::TestEquityCurvePanel::test_renders_canvas_and_data_island` | ✅ COMPLIANT |
| 4 | REQ-WEB-2: Empty-state when no snapshots | `test_web.py::TestEquityCurvePanel::test_empty_state_when_no_snapshots` | ✅ COMPLIANT |
| 5 | REQ-WEB-3: Lists open trades only (DESC by opened_at, no closed) | `test_web.py::TestOpenPositionsPanel::test_lists_open_trades_in_descending_opened_at` (DESC order verified at store level by test #5 in storage) | ✅ COMPLIANT |
| 6 | REQ-WEB-3: Empty-state when no open trades | `test_web.py::TestOpenPositionsPanel::test_empty_state_when_no_open_trades` | ✅ COMPLIANT |
| 7 | REQ-WEB-4: Caps result at 500 rows | `test_store.py::TestPaperTradeRepo::test_get_all_paper_trades_caps_at_default_limit` (route uses `limit=500` — see `routes.py::panel_trade_history` L106) | ✅ COMPLIANT |
| 8 | REQ-WEB-4: Orders DESC by opened_at | `test_store.py::TestPaperTradeRepo::test_get_all_paper_trades_orders_desc_by_opened_at` | ✅ COMPLIANT |
| 9 | REQ-WEB-4: Empty-state when no trades | `test_web.py::TestTradeHistoryPanel::test_empty_state_when_no_trades` | ✅ COMPLIANT |
| 10 | REQ-WEB-5: Lists all wallets ordered by rank | `test_store.py::TestWalletRepo::test_get_all_ordered_by_rank` (storage-level ordering); `test_web.py::TestWalletsPanel::test_renders_seeded_wallet` (route renders) | ✅ COMPLIANT |
| 11 | REQ-WEB-5: Empty-state when no wallets | `test_web.py::TestWalletsPanel::test_empty_state_when_no_wallets` | ✅ COMPLIANT |
| 12 | REQ-WEB-6: Sums current_value of open trades | `test_web.py::TestMoneyInOpenPanel::test_sums_current_value_of_open_trades` (asserts `3.50`) | ✅ COMPLIANT |
| 13 | REQ-WEB-6: Shows 0.00 when no open trades | `test_web.py::TestMoneyInOpenPanel::test_shows_zero_when_no_open_trades` | ✅ COMPLIANT |
| 14 | REQ-WEB-7: Computes unrealized PnL (signed) | `test_web.py::TestPnlOpenPanel::test_computes_signed_unrealized_pnl` (asserts `+0.80`) | ✅ COMPLIANT |
| 15 | REQ-WEB-7: Shows 0.00 when no open trades | `test_web.py::TestPnlOpenPanel::test_shows_zero_when_no_open_trades` | ✅ COMPLIANT |
| 16 | REQ-WEB-8: Sums PnL of closed trades (signed) | `test_web.py::TestPnlHistoricalPanel::test_sums_signed_realized_pnl` (asserts `+1.25`) | ✅ COMPLIANT |
| 17 | REQ-WEB-8: Shows 0.00 when no closed trades | `test_web.py::TestPnlHistoricalPanel::test_shows_zero_when_no_closed_trades` | ✅ COMPLIANT |
| 18 | REQ-WEB-9: Panel HTML contains 5s trigger (≥7×) | `test_web.py::TestServingAndBind::test_index_contains_every_5s_trigger_at_least_7_times` | ✅ COMPLIANT |
| 19 | REQ-WEB-10: Static file served at vendor path | `test_web.py::TestServingAndBind::test_vendor_chart_umd_is_served_from_static` | ✅ COMPLIANT |
| 20 | REQ-WEB-10: No CDN host in rendered HTML | `test_web.py::TestServingAndBind::test_index_does_not_reference_cdn_hosts` | ✅ COMPLIANT |
| 21 | REQ-WEB-11: All panels with empty DB render placeholder | Covered by 5 individual empty-state tests (scenarios 4, 6, 9, 11, 15, 17) | ✅ COMPLIANT |
| 22 | REQ-WEB-12: Stylesheet is served and linked | `test_web.py::TestServingAndBind::test_css_includes_neon_and_monospace_markers` (CSS served) + implicit `<link>` via `base.html` L7 (no explicit assertion of the `<link>` tag in the index body) | ⚠️ PARTIAL |
| 23 | REQ-WEB-12: CSS includes neon + monospace markers | `test_web.py::TestServingAndBind::test_css_includes_neon_and_monospace_markers` (asserts `#0ff` / `#8b5cf6` + monospace tokens) | ✅ COMPLIANT |
| 24 | REQ-WEB-13: Default bind address is loopback | `test_web.py::TestBindAddress::test_main_module_passes_loopback_host` (asserts `host="127.0.0.1"`, `port=8000`, and that `"0.0.0.0" not in str(call)`) | ✅ COMPLIANT |
| 25 | REQ-WEB-14: Mutating methods rejected | `test_web.py::TestServingAndBind::test_post_to_index_is_rejected_with_405` (loops over `/`, `/api/panel/equity-curve`, `/api/panel/wallets`) | ✅ COMPLIANT |

**Compliance summary**: 32/33 COMPLIANT, 1/33 PARTIAL (REQ-WEB-12 first sub-scenario: the `<link>` tag presence in the index body is not explicitly asserted, only inferred from the CSS being served).

## Design Coherence

| Design Decision (from design.md) | Implementation Evidence | Status |
|-----------------------------------|-------------------------|--------|
| 1. Single `routes.py` (1 `APIRouter`, 8 endpoints) | `src/copytrading/web/routes.py` (224 lines, 1 `router = APIRouter()`, 8 GET handlers: index + 7 panels) | ✅ |
| 2. Equity-curve data as HTML data island | `routes.py::_equities_json()` + `panels/equity_curve.html` L4 (`<script type="application/json" id="equity-data">`) | ✅ |
| 3. Decimal serialization: route builds `list[str]`, template `tojson`s | `routes.py::_equities_json()` uses `str(s.equity) for s in snapshots`; aggregate cards use `format_signed(Decimal, ...)` returning `str` | ✅ |
| 4. `create_app(db_path)` factory + per-request `get_store` dep | `app.py::create_app()` (L50-69) + `get_store()` (L33-44) with `with Store(...) as store: yield store` | ✅ |
| 5. Bind to `127.0.0.1:8000` via `__main__.py` | `__main__.py::main()` (L16-30) with `host="127.0.0.1", port=8000`; test `TestBindAddress::test_main_module_passes_loopback_host` asserts both | ✅ |
| 6. Vendored HTMX + Chart.js under `static/vendor/` | `web/static/vendor/htmx.min.js` (48,101 B) + `web/static/vendor/chart.umd.min.js` (205,615 B) + `NOTICE` (MIT+BSD-2 attribution) | ✅ |
| 7. Chart re-render via single `htmx:afterSwap` listener in `dashboard.js` reading `#equity-data` island | `static/js/dashboard.js` L48-61 (single global listener); `renderEquityChart` holds module-scoped `chartInstance`, calls `chart.update()` on subsequent swaps (L19-23) | ✅ |
| Data layer: `get_all_snapshots()` (ASC) and `get_all_paper_trades(limit=500)` (DESC, LIMIT at SQL) | `store.py::get_all_snapshots` (L482-497, `ORDER BY snapshot_at ASC`); `store.py::get_all_paper_trades` (L397-449, `ORDER BY opened_at DESC LIMIT ?`) | ✅ |
| 3 aggregate cards use `SUM(CAST(... AS REAL))` per spec, `Decimal(str(row[0]))` recovery | `routes.py::_sum_open_current_value`, `_sum_open_unrealized`, `_sum_closed_pnl` (L143-165) | ✅ |
| DecimalEncoder as canonical home for any future JSON endpoint | `encoders.py::DecimalEncoder` (kept per design §3) | ✅ |
| **`format_signed` helper (NEW, not in design.md)** | `formatting.py::format_signed(value, places=2, *, signed=True) -> str` — used by all 3 aggregate cards | ⚠️ Design coherence item (not a spec violation) |
| **`__main__.py` hardcodes `db_path="copytrading.db"`** | `__main__.py::main()` L27: `create_app(db_path="copytrading.db")` | ⚠️ Design deviation (no spec scenario mandates configurability) |
| **`wallets.username` field in `models.Wallet` but no `username` column in `wallets` table** | `models.py::Wallet` (has `username: str = ""`); `store.py` schema (no `username` column); `templates/panels/wallets.html` L16 falls back to `address[:10] + "…"` | ⚠️ Pre-existing core-infra debt, not web-dashboard |

## Issues (Re-verified 2026-06-08)

### CRITICAL

None.

### WARNING

None — all 3 previous WARNINGs resolved.

### SUGGESTION

1. **TDD Cycle Evidence table missing from apply-progress.** The strict-tdd-verify.md template expects a per-task RED/GREEN/TRIANGULATE/SAFETY NET/REFACTOR table. The actual apply-progress #165 is a recovery note with `[test-first]` tags in tasks.md serving as proxy evidence. Recommended for process improvement, not blocking.

2. **sdd-apply sub-agent empty-return pattern** (Slice 1 and Slice 3 both returned empty despite completing the work correctly). Investigate the delegation prompt for the agent — appears to load `sdd-apply` via the `skill()` tool, triggering the ORCHESTRATOR GATE that tells it to stop. Process improvement, not blocking.

## Final Verdict

**PASS**

All 33 spec scenarios are COMPLIANT with passing runtime tests. All 4 previous WARNINGs and 1 PARTIAL resolved in 9 follow-up commits. Full quality gate green: 145/145 tests, mypy strict clean, ruff check + format clean. Working tree clean, 23 implementation commits on `master`/`origin/master`. The SQLite thread-safety bug (showstopper found during Playwright testing) is fixed with `check_same_thread=False`.

Ready for `sdd-archive`.
3. **Process improvement (not blocking):** investigate the recurring sdd-apply sub-agent empty-return pattern; mandate a TDD Cycle Evidence table in apply-progress even on recovery.

## Relevant Files

| File | Role |
|------|------|
| `openspec/changes/web-dashboard/proposal.md` | Intent, scope, success criteria |
| `openspec/changes/web-dashboard/specs/web-dashboard/spec.md` | 14 REQ-WEB-N, 25 scenarios |
| `openspec/changes/web-dashboard/specs/storage/spec.md` | 2 ADDED REQ-STORAGE-NEW-N, 8 scenarios |
| `openspec/changes/web-dashboard/design.md` | Architecture, 7 decisions, file changes |
| `openspec/changes/web-dashboard/tasks.md` | 20 tasks, 3 PR slices, all `[x]` |
| `src/copytrading/store.py` (L397-449, L482-497) | 2 new methods: `get_all_paper_trades`, `get_all_snapshots` |
| `src/copytrading/web/__init__.py` | Exports `create_app` |
| `src/copytrading/web/app.py` | `create_app(db_path)` factory, `get_store` dep |
| `src/copytrading/web/routes.py` | 1 `APIRouter`, 8 GET handlers (index + 7 panels) |
| `src/copytrading/web/__main__.py` | `uvicorn.run(..., host="127.0.0.1", port=8000)` |
| `src/copytrading/web/encoders.py` | `DecimalEncoder` (utility, tested independently) |
| `src/copytrading/web/formatting.py` | `format_signed` helper (new, not in design) |
| `src/copytrading/web/templates/{base,index}.html` | HTML5 shell, 7 panel placeholders, 7 `every 5s` triggers |
| `src/copytrading/web/templates/panels/*.html` | 7 panel partials + `partials/empty_state.html` |
| `src/copytrading/web/static/css/dashboard.css` | Dark/neon theme, monospace, backdrop-filter |
| `src/copytrading/web/static/js/dashboard.js` | `htmx:afterSwap` → `renderEquityChart` via data island |
| `src/copytrading/web/static/vendor/{htmx.min.js,chart.umd.min.js,NOTICE}` | Vendored JS + license attribution |
| `tests/unit/test_web.py` (594 lines) | 27 integration tests covering all 25 web-dashboard scenarios + 5 format_signed unit tests |
| `tests/unit/test_web_decimal_encoder.py` | 2 unit tests for DecimalEncoder |
| `tests/unit/test_store.py` | 8 new tests (3 for get_all_snapshots, 5 for get_all_paper_trades) |
| `README.md` | "Run the dashboard" section (T3.4) |
| `openspec/changes/web-dashboard/verify-report.md` | This file (hybrid persistence) |
