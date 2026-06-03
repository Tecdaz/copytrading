# Proposal: core-infrastructure

## Intent

Paper-trading foundation for three cronjobs (`leaderboard_discovery`, `position_copier`, `account_tracker`): typed config, domain models, SQLite store, **read-only** Polymarket public-API client (no auth), Google Sheets writer, 0.5% risk sizing on **simulated** USDC. PAPER only — no real orders, no signing, no `py-clob-client`. We read public markets + public wallet positions, simulate copy trades locally, report to Sheets. Paper balance starts at **200 USDC**.

## Scope

### In Scope

1. `src/copytrading/config.py` — `python-dotenv` → frozen `Settings`; **2 keys**: `GOOGLE_SHEETS_CREDENTIALS_PATH`, `GOOGLE_SHEET_ID`. No Polymarket credentials.
2. `src/copytrading/models.py` — frozen dataclasses: `Wallet`, `Position`, `Market`, `PaperTrade`, `AccountSnapshot`. `PaperTrade`: `copied_from_wallet`, `market`, `side`, `size`, `entry_price`, `status` (open/closed), `pnl`.
3. `src/copytrading/store.py` — SQLite schema (`wallets`, `positions`, `markets`, `paper_trades`, `account_snapshots`) + `Store` + repos. WAL mode.
4. `src/copytrading/poly_client.py` — **read-only** `httpx` over Polymarket CLOB public REST: `get_markets()`, `get_market(condition_id)`, `get_positions(wallet_address)`, `get_orderbook(token_id)`. No auth, no signing.
5. `src/copytrading/sheets_client.py` — wrapper over `googleapiclient` + service-account creds.
6. `src/copytrading/risk.py` — `calculate_position_size(account_equity, risk_pct=Decimal("0.005"))` → Decimal USDC.
7. `tests/conftest.py` — `FakeHTTPClient` + `FakeSheetsService`.

### Out of Scope

- Cronjob scripts. Real orders / fills / Polymarket auth. Migration framework.

## Capabilities

> Researched `openspec/specs/` — only `tooling/` exists; no overlap.

### New

- `storage`: SQLite schema (incl. `paper_trades`) + repos.
- `config`: typed env loader, 2 keys, fail-fast.
- `polymarket-public-client`: read-only `httpx` over CLOB public REST.
- `google-sheets-client`: typed wrapper over `google-api-python-client`.
- `risk`: 0.5% sizing math for paper USDC.
- `paper-trading`: `PaperTrade` model + lifecycle (open/closed/pnl).

### Modified

- `tooling` (delta): drops `py-clob-client`; adds `httpx`; trims `.env.example` to 2 keys.

## Approach

- **`httpx` not `py-clob-client`** — public endpoints need no signing.
- **Dataclasses, not Pydantic** — mypy strict covers the contract.
- **`sqlite3` stdlib, not SQLAlchemy** — five tables; ORM overkill.
- **Repository methods on `Store`** — single transaction seam, easy fakes.
- **Fakes over mocks** — `FakeHTTPClient` + `FakeSheetsService`.
- **`Decimal` for paper money** — no float drift on sizing / P&L.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/copytrading/config.py` | New | Settings + `from_env()`; 2 keys. |
| `src/copytrading/models.py` | New | 5 frozen dataclasses incl. `PaperTrade`. |
| `src/copytrading/store.py` | New | Schema (5 tables) + `Store` + repos. |
| `src/copytrading/poly_client.py` | New | Read-only `httpx`; 4 methods. |
| `src/copytrading/sheets_client.py` | New | `SheetsClient` over google API. |
| `src/copytrading/risk.py` | New | `calculate_position_size` for paper USDC. |
| `tests/conftest.py` + `tests/unit/**` | New | Fakes + per-module tests. |
| `pyproject.toml` | Modified | Remove `py-clob-client`; add `httpx`. |
| `.env.example` | Modified | Trim to 2 keys. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Polymarket CLOB public API response-shape drift | Med | Pin models; one network-gated integration test. |
| Rate limiting on public endpoints | Med | `httpx` retry/backoff; cap concurrency. |
| Decimal drift in 0.5% sizing / P&L | Low | `Decimal` throughout. |
| `PaperTrade` mistaken for real trades | Low | `paper_` prefix; comment block. |
| Secrets via `Settings.__repr__` | Low | Frozen dataclass; no override. |
| SQLite write contention | Low | WAL mode; separate run windows. |

## PR Split

Total ≈ 350 LoC + ~200 tests. **Under 400-line budget → single PR recommended**. Work has a natural split (foundation vs. IO) but paper-trading semantics are coherent; splitting risks partial-merge confusion. Revert stays one operation.

## Rollback Plan

No live state, no auth, no real money. Reverting deletes the six new files + tests; project returns to `__version__`-only. First `copytrading.db` lands only when a consumer change calls `Store(...)` — partial merge is safe to revert.

## Dependencies

- `bootstrap-tooling` (archived) — uv, ruff, mypy, pytest in `uv.lock`.
- `httpx` — public-API HTTP client (replaces `py-clob-client`).
- `google-api-python-client` + `google-auth` — Sheets writer.
- `python-dotenv` — `.env` loader.
- **Removed**: `py-clob-client` (no auth needed).

## Success Criteria

- [ ] `uv run pytest` / `mypy src tests` / `ruff check .` / `ruff format --check .` all exit 0.
- [ ] `Settings.from_env()` raises on missing key (2 keys: `GOOGLE_SHEETS_CREDENTIALS_PATH`, `GOOGLE_SHEET_ID`).
- [ ] `risk.calculate_position_size(Decimal("200"), Decimal("0.005")) == Decimal("1.00")`.
- [ ] `Store` creates 5 tables (incl. `paper_trades`) on first connect; in-memory test proves schema.
- [ ] `PolyClient` exposes exactly 4 read-only methods; no `place_*` / `cancel_*` / `create_order` / `post_order`.
- [ ] `FakeHTTPClient` + `FakeSheetsService` importable from `tests.conftest`.
- [ ] `poly_client` + `sheets_client` do NOT import `os.environ` directly.
- [ ] `pyproject.toml` no longer lists `py-clob-client`; `.env.example` has exactly 2 keys.
