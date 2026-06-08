# Storage

Merged from `openspec/changes/web-dashboard/specs/storage/spec.md` (2026-06-08).

## Requirements

### Requirement: Get all account snapshots

`Store` SHALL provide `get_all_snapshots() -> list[AccountSnapshot]`
returning every row in `account_snapshots` ordered ASC by `snapshot_at`.
When the table is empty, the method SHALL return an empty list (not
`None`).

#### Scenario: Returns snapshots in chronological order
- **Given** a `Store` with 3 snapshots at times T1, T2, T3 (inserted in that order)
- **When** `store.get_all_snapshots()` is called
- **Then** the returned list SHALL contain 3 `AccountSnapshot` instances
- **And** they SHALL be ordered such that `result[0].snapshot_at < result[1].snapshot_at < result[2].snapshot_at`

#### Scenario: Returns empty list when no snapshots exist
- **Given** a `Store` with an empty `account_snapshots` table
- **When** `store.get_all_snapshots()` is called
- **Then** the returned value SHALL be an empty list (not `None`)

#### Scenario: Decimals round-trip from TEXT storage
- **Given** a snapshot inserted with `equity=Decimal("200.50")` and `total_pnl=Decimal("12.34")`
- **When** `store.get_all_snapshots()` is called
- **Then** the returned snapshot's `equity` SHALL equal `Decimal("200.50")`
- **And** its `total_pnl` SHALL equal `Decimal("12.34")`

### Requirement: Get recent paper trades

`Store` SHALL provide `get_all_paper_trades(limit: int = 500) ->
list[PaperTrade]` returning the most recent rows from `paper_trades`
ordered DESC by `opened_at`, capped at `limit` rows. The `limit`
parameter SHALL be required (no `None`/no-cap behavior) and SHALL be
enforced server-side at the SQL layer.

#### Scenario: Caps result at the limit
- **Given** 600 rows in `paper_trades` with distinct `opened_at` values
- **When** `store.get_all_paper_trades(limit=500)` is called
- **Then** the returned list SHALL contain exactly 500 entries

#### Scenario: Orders DESC by opened_at
- **Given** 3 rows with `opened_at` = T1, T2, T3 (T1 < T2 < T3)
- **When** `store.get_all_paper_trades(limit=500)` is called
- **Then** the returned list SHALL be ordered T3, T2, T1

#### Scenario: Honors a smaller limit
- **Given** 5 rows in `paper_trades`
- **When** `store.get_all_paper_trades(limit=2)` is called
- **Then** the returned list SHALL contain exactly 2 entries (the 2 most recent)

#### Scenario: Returns empty list when no trades exist
- **Given** a `Store` with an empty `paper_trades` table
- **When** `store.get_all_paper_trades()` is called
- **Then** the returned value SHALL be an empty list (not `None`)

#### Scenario: Limit is enforced at SQL level, not post-fetch
- **Given** 1000 rows in `paper_trades`
- **When** `store.get_all_paper_trades(limit=10)` is called
- **Then** the SQL query SHALL include `LIMIT 10` (verifiable by
  inspecting the executed statement or by counting intermediate rows
  fetched)
