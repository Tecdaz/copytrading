# Design: core-infrastructure

## Architecture Decisions

### D1: httpx over py-clob-client
**Decision**: Use `httpx` directly for Polymarket public API.
**Rationale**: Public endpoints require no signing/auth. `py-clob-client` adds signing overhead we don't need. `httpx` is modern, supports async if needed later, and gives us full control over request/response handling.
**Tradeoff**: We maintain our own endpoint URLs vs. getting them from the SDK.

### D2: Dataclasses over Pydantic
**Decision**: Use stdlib `dataclasses` with `frozen=True`.
**Rationale**: mypy strict mode catches type errors at check time. No runtime validation framework needed for internal models. Fewer dependencies.
**Tradeoff**: No automatic serialization/deserialization — we handle it manually.

### D3: stdlib sqlite3 over SQLAlchemy
**Decision**: Use `sqlite3` directly with a `Store` class.
**Rationale**: 5 simple tables. ORM adds complexity without value. Repository pattern provides testability.
**Tradeoff**: Manual SQL, but it's straightforward for this schema.

### D4: Decimal for Money Math
**Decision**: Use `Decimal` for all USDC amounts and risk calculations.
**Rationale**: Float arithmetic causes drift (0.1 + 0.2 != 0.3). `Decimal` is exact for financial calculations.
**Tradeoff**: Slightly more verbose code, but correctness matters.

### D5: Repository Pattern on Store
**Decision**: Single `Store` class with repository methods (not separate repo classes).
**Rationale**: Simple composition. One connection, one transaction seam. Easy to fake in tests.
**Tradeoff**: Store class grows with methods, but it's still manageable for 5 tables.

### D6: Fakes over Mocks
**Decision**: `FakeHTTPClient` and `FakeSheetsService` in `conftest.py`.
**Rationale**: Deterministic tests, no mock framework dependency, clear test doubles.
**Tradeoff**: More code to maintain fakes, but tests are more readable.

### D7: Settings.from_env() Fail-Fast
**Decision**: Raise `ValueError` immediately if required env vars are missing.
**Rationale**: Fail at startup, not mid-cronjob. Clear error messages.
**Tradeoff**: No graceful degradation, but cronjobs should fail loudly.

## Module Dependency Graph

```
config.py (no deps)
    ↓
models.py (no deps, uses Decimal)
    ↓
store.py (depends on models)
poly_client.py (depends on models, uses httpx)
sheets_client.py (depends on models, config, uses googleapiclient)
risk.py (depends on models, uses Decimal)
```

## SQLite Schema

```sql
CREATE TABLE IF NOT EXISTS wallets (
    address TEXT PRIMARY KEY,
    rank INTEGER NOT NULL,
    total_pnl REAL NOT NULL,
    discovered_at TEXT NOT NULL,
    last_checked_at TEXT
);

CREATE TABLE IF NOT EXISTS markets (
    condition_id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    token_id_yes TEXT,
    token_id_no TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_address TEXT NOT NULL REFERENCES wallets(address),
    market_condition_id TEXT NOT NULL REFERENCES markets(condition_id),
    side TEXT NOT NULL CHECK(side IN ('yes', 'no')),
    size REAL NOT NULL,
    avg_price REAL NOT NULL,
    fetched_at TEXT NOT NULL,
    UNIQUE(wallet_address, market_condition_id, side)
);

CREATE TABLE IF NOT EXISTS paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    copied_from_wallet TEXT NOT NULL REFERENCES wallets(address),
    market_condition_id TEXT NOT NULL REFERENCES markets(condition_id),
    side TEXT NOT NULL CHECK(side IN ('yes', 'no')),
    size REAL NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL,
    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'closed')),
    pnl REAL DEFAULT 0,
    opened_at TEXT NOT NULL,
    closed_at TEXT
);

CREATE TABLE IF NOT EXISTS account_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equity REAL NOT NULL,
    open_trades INTEGER NOT NULL,
    total_pnl REAL NOT NULL DEFAULT 0,
    snapshot_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_paper_trades_status ON paper_trades(status);
CREATE INDEX IF NOT EXISTS idx_paper_trades_wallet ON paper_trades(copied_from_wallet);
CREATE INDEX IF NOT EXISTS idx_positions_wallet ON positions(wallet_address);
```

## Polymarket Public API Endpoints

Base URL: `https://clob.polymarket.com`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/markets` | List all markets |
| GET | `/markets/{condition_id}` | Get single market |
| GET | `/positions/{wallet_address}` | Get wallet positions (public) |
| GET | `/book` | Get orderbook for a token |

## PaperTrade Lifecycle

```
1. Cronjob detects wallet opened position
2. risk.calculate_position_size(equity) → size
3. Store.insert_paper_trade(status="open", entry_price=market_price)
4. Cronjob detects wallet closed position
5. Store.update_paper_trade_status(id, "closed", exit_price, pnl)
```

## Error Handling Strategy

- `PolyClientError(Exception)` — wraps httpx errors and invalid responses
- `SheetsClientError(Exception)` — wraps Google API errors
- `ConfigError(ValueError)` — missing/invalid env vars
- Store methods raise `sqlite3.Error` subclasses — callers handle or log

## Connection Lifecycle

```python
with Store("copytrading.db") as store:
    store.upsert_wallet(...)
    store.insert_paper_trade(...)
# connection auto-closed
```
