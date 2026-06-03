# Spec: storage

## ADDED Requirements

### REQ-STORAGE-1: SQLite Schema
The system SHALL create 5 tables on first connection: `wallets`, `positions`, `markets`, `paper_trades`, `account_snapshots`.

#### Scenario: Schema creation on first connect
- **Given** a new SQLite database file
- **When** `Store` is instantiated with that path
- **Then** all 5 tables MUST exist with correct columns

### REQ-STORAGE-2: WAL Mode
The system SHALL enable WAL journal mode for concurrent read safety.

#### Scenario: WAL mode enabled
- **Given** a `Store` instance
- **When** the connection is opened
- **Then** `PRAGMA journal_mode` MUST return `wal`

### REQ-STORAGE-3: Context Manager
`Store` SHALL implement `__enter__` and `__exit__` for connection lifecycle.

#### Scenario: Context manager usage
- **Given** a `Store` instance
- **When** used in a `with` block
- **Then** the connection MUST be open inside the block and closed on exit

### REQ-STORAGE-4: Wallet Repository
The system SHALL provide `upsert_wallet` and `get_all_wallets` methods.

#### Scenario: Upsert and retrieve wallets
- **Given** a `Store` with an empty `wallets` table
- **When** `upsert_wallet(address="0xabc", rank=1, pnl=Decimal("100"))` is called
- **Then** `get_all_wallets()` MUST return a list containing that wallet

### REQ-STORAGE-5: Paper Trade Repository
The system SHALL provide `insert_paper_trade`, `update_paper_trade_status`, and `get_open_paper_trades` methods.

#### Scenario: Paper trade lifecycle
- **Given** a `Store` with an empty `paper_trades` table
- **When** a paper trade is inserted with status "open"
- **And** `update_paper_trade_status(trade_id, "closed", pnl=Decimal("0.50"))` is called
- **Then** `get_open_paper_trades()` MUST NOT include that trade

### REQ-STORAGE-6: Account Snapshot Repository
The system SHALL provide `insert_account_snapshot` and `get_latest_snapshot` methods.

#### Scenario: Track account equity over time
- **Given** a `Store` with snapshots
- **When** `insert_account_snapshot(equity=Decimal("200"), timestamp=...)` is called
- **Then** `get_latest_snapshot()` MUST return the most recent snapshot
