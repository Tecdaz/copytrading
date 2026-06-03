# Spec: paper-trading

## ADDED Requirements

### REQ-PAPER-1: PaperTrade Model
`PaperTrade` SHALL be a frozen dataclass with fields: `id`, `copied_from_wallet`, `market_id`, `side`, `size`, `entry_price`, `status`, `pnl`, `opened_at`, `closed_at`.

#### Scenario: Create a paper trade
- **Given** valid parameters
- **When** a `PaperTrade` is instantiated
- **Then** all fields MUST be accessible as attributes

### REQ-PAPER-2: Status Values
`status` SHALL be one of: `"open"`, `"closed"`.

#### Scenario: Valid status
- **Given** `status="open"`
- **When** a `PaperTrade` is created
- **Then** the status MUST be accepted

### REQ-PAPER-3: PnL Calculation
When a trade is closed, `pnl` SHALL reflect the profit/loss in USDC.

#### Scenario: Profitable trade
- **Given** entry_price=0.50, exit_price=0.60, size=10
- **When** the trade is closed
- **Then** `pnl` MUST be `Decimal("1.00")` (positive)

#### Scenario: Losing trade
- **Given** entry_price=0.50, exit_price=0.40, size=10
- **When** the trade is closed
- **Then** `pnl` MUST be `Decimal("-1.00")` (negative)

### REQ-PAPER-4: Paper Prefix Convention
All paper-trading identifiers SHALL use `paper_` prefix to distinguish from real trades.

#### Scenario: Table naming
- **Given** the SQLite schema
- **When** inspecting table names
- **Then** the trades table MUST be named `paper_trades`
