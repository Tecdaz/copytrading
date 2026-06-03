# Tasks: core-infrastructure

## Phase 1: Foundation (no IO)

- [ ] **Task 1.1**: Create `src/copytrading/models.py` with frozen dataclasses: `Wallet`, `Position`, `Market`, `PaperTrade`, `AccountSnapshot`. Use `Decimal` for all money fields.
- [ ] **Task 1.2**: Create `src/copytrading/config.py` with `Settings` dataclass and `from_env()` classmethod. Load `GOOGLE_SHEETS_CREDENTIALS_PATH` (Path) and `GOOGLE_SHEET_ID` (str). Raise `ValueError` on missing keys.
- [ ] **Task 1.3**: Create `src/copytrading/risk.py` with `calculate_position_size(account_equity: Decimal, risk_pct: Decimal = Decimal("0.005")) -> Decimal` and `validate_trade(amount: Decimal, equity: Decimal) -> bool`.
- [ ] **Task 1.4**: Write unit tests for models, config, and risk in `tests/unit/`. Test Decimal precision, fail-fast config, 0.5% math.

## Phase 2: Storage

- [ ] **Task 2.1**: Create `src/copytrading/store.py` with `Store` class. Implement `__init__`, `__enter__`, `__exit__`, WAL mode pragma.
- [ ] **Task 2.2**: Implement schema creation (5 tables + indexes) in `Store.__init__`.
- [ ] **Task 2.3**: Implement wallet repo methods: `upsert_wallet`, `get_all_wallets`.
- [ ] **Task 2.4**: Implement paper trade repo methods: `insert_paper_trade`, `update_paper_trade_status`, `get_open_paper_trades`.
- [ ] **Task 2.5**: Implement account snapshot methods: `insert_account_snapshot`, `get_latest_snapshot`.
- [ ] **Task 2.6**: Write unit tests for Store using in-memory SQLite (`:memory:`).

## Phase 3: External Clients

- [ ] **Task 3.1**: Remove `py-clob-client` from `pyproject.toml`, add `httpx`. Run `uv sync`.
- [ ] **Task 3.2**: Create `src/copytrading/poly_client.py` with `PolyClient` class using `httpx`. Implement 4 read-only methods: `get_markets`, `get_market`, `get_positions`, `get_orderbook`. Define `PolyClientError`.
- [ ] **Task 3.3**: Create `src/copytrading/sheets_client.py` with `SheetsClient` class. Implement `from_settings`, `update_leaderboard`, `append_trades`, `update_account`. Define `SheetsClientError`.
- [ ] **Task 3.4**: Create `tests/conftest.py` with `FakeHTTPClient` and `FakeSheetsService` classes.
- [ ] **Task 3.5**: Write unit tests for `poly_client` and `sheets_client` using fakes.

## Phase 4: Cleanup

- [ ] **Task 4.1**: Update `.env.example` to only 2 keys: `GOOGLE_SHEETS_CREDENTIALS_PATH` and `GOOGLE_SHEET_ID`.
- [ ] **Task 4.2**: Run full verification: `uv sync && uv run ruff check . && uv run ruff format . && uv run mypy src tests && uv run pytest`. All exit 0.

## Dependencies

```
Phase 1 → Phase 2 → Phase 3 → Phase 4
```

Phase 1 has no IO deps. Phase 2 depends on models. Phase 3 depends on models + config. Phase 4 is final cleanup.

## Estimated Lines

| Phase | Source | Tests | Total |
|-------|--------|-------|-------|
| 1 | ~80 | ~60 | ~140 |
| 2 | ~100 | ~80 | ~180 |
| 3 | ~120 | ~80 | ~200 |
| 4 | ~5 | 0 | ~5 |
| **Total** | **~305** | **~220** | **~525** |

## Review Workload Forecast

- Estimated changed lines: ~525
- 400-line budget risk: **Medium** (slightly over)
- Chained PRs recommended: **Yes** (force-chained strategy)
- Suggested split: PR 1 (Phase 1+2, ~320 lines) → PR 2 (Phase 3+4, ~205 lines)
