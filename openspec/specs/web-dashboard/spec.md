# Web Dashboard Specification

## Purpose

A read-only FastAPI + Jinja2 + HTMX web panel that observes the live SQLite
database over 7 panels. No writes, no auth, no trading logic. Polls every 5s.

## Requirements

### Requirement: Index page renders 7 panels

The system SHALL serve `GET /` returning an HTML page that contains the 7
panel placeholders (equity curve, open positions, trade history, tracked
wallets, money in open positions, PnL of open positions, historical PnL),
each with an HTMX polling hook (`hx-get`, `hx-trigger="every 5s"`).

#### Scenario: Index returns 200 with all 7 panels present
- **Given** a running app with an empty database
- **When** the client requests `GET /`
- **Then** the response SHALL be HTTP 200 with `text/html`
- **And** the body SHALL contain the 7 panel section identifiers

#### Scenario: Index renders with populated database
- **Given** a `Store` containing 1 wallet, 1 open trade, and 1 snapshot
- **When** the client requests `GET /`
- **Then** the response SHALL be HTTP 200
- **And** each panel section SHALL be present (empty-state copy allowed if no data)

### Requirement: Equity curve panel

The system SHALL expose `GET /api/panel/equity-curve` returning an HTML
fragment containing a `<canvas id="equity-chart">` and a JSON data island
(`<script type="application/json" id="equity-data">`) whose body is the
`equity` field of every `account_snapshots` row, ordered ASC by `snapshot_at`.

#### Scenario: Renders chart data for populated snapshots
- **Given** 3 snapshots in `account_snapshots` with equities `200`, `205`, `210`
- **When** the client requests `GET /api/panel/equity-curve`
- **Then** the response SHALL be HTTP 200 with `text/html`
- **And** the data island SHALL contain the 3 equities in ASC order

#### Scenario: Empty-state when no snapshots
- **Given** an empty `account_snapshots` table
- **When** the client requests `GET /api/panel/equity-curve`
- **Then** the response SHALL render the empty-state placeholder copy
- **And** the data island SHALL contain an empty array

### Requirement: Open positions panel

The system SHALL expose `GET /api/panel/open-positions` returning an HTML
`<table>` fragment with one row per `paper_trades WHERE status='open'`,
displaying `market_title`, `side`, `current_value`, `percent_pnl`,
`opened_at`. Rows SHALL be sorted DESC by `opened_at`.

#### Scenario: Lists open trades only
- **Given** 2 open trades and 1 closed trade in `paper_trades`
- **When** the client requests `GET /api/panel/open-positions`
- **Then** the response SHALL contain exactly 2 rows
- **And** neither row SHALL be the closed trade

#### Scenario: Empty-state when no open trades
- **Given** 0 open trades
- **When** the client requests `GET /api/panel/open-positions`
- **Then** the response SHALL render the empty-state placeholder

### Requirement: Trade history panel

The system SHALL expose `GET /api/panel/trade-history` returning an HTML
`<table>` fragment with the most recent 500 `paper_trades`, sorted DESC by
`opened_at`. Display columns: `opened_at`, `market_title`, `side`,
`entry_price`, `exit_price`, `pnl`, `status`.

#### Scenario: Caps result at 500 rows
- **Given** 600 rows in `paper_trades`
- **When** the client requests `GET /api/panel/trade-history`
- **Then** the response SHALL contain at most 500 rows

#### Scenario: Orders DESC by opened_at
- **Given** 3 trades with `opened_at` = T1 < T2 < T3
- **When** the client requests `GET /api/panel/trade-history`
- **Then** the first row SHALL be T3, the second T2, the third T1

#### Scenario: Empty-state when no trades
- **Given** an empty `paper_trades` table
- **When** the client requests `GET /api/panel/trade-history`
- **Then** the response SHALL render the empty-state placeholder

### Requirement: Tracked wallets panel

The system SHALL expose `GET /api/panel/wallets` returning an HTML fragment
with one row per row in the `wallets` table, sorted ASC by `rank`. Display
columns: `rank`, `username` (or truncated `address`), `total_pnl`,
`last_checked_at` (formatted as ISO date or "never" when NULL).

#### Scenario: Lists all wallets ordered by rank
- **Given** 3 wallets with ranks 2, 1, 3 in `wallets`
- **When** the client requests `GET /api/panel/wallets`
- **Then** the response SHALL contain 3 rows in rank order 1, 2, 3

#### Scenario: Empty-state when no wallets
- **Given** an empty `wallets` table
- **When** the client requests `GET /api/panel/wallets`
- **Then** the response SHALL render the empty-state placeholder

### Requirement: Money in open positions card

The system SHALL expose `GET /api/panel/money-in-open` returning an HTML
fragment showing `SUM(CAST(current_value AS REAL))` of all
`paper_trades WHERE status='open'` formatted as a USDC string with 2
decimals, or `0.00` when the table has no open trades.

#### Scenario: Sums current_value of open trades
- **Given** 2 open trades with `current_value` = `1.00` and `2.50`
- **When** the client requests `GET /api/panel/money-in-open`
- **Then** the response SHALL display `3.50` USDC

#### Scenario: Shows 0.00 when no open trades
- **Given** 0 open trades
- **When** the client requests `GET /api/panel/money-in-open`
- **Then** the response SHALL display `0.00` USDC

### Requirement: PnL of open positions card

The system SHALL expose `GET /api/panel/pnl-open` returning an HTML
fragment showing `SUM(CAST(current_value AS REAL) - CAST(initial_value AS
REAL))` of all `paper_trades WHERE status='open'`, formatted as a USDC
string with 2 decimals (signed, e.g. `+1.23` or `-0.50`).

#### Scenario: Computes unrealized PnL
- **Given** 2 open trades: (current=2.00, initial=1.00) and (current=0.80, initial=1.00)
- **When** the client requests `GET /api/panel/pnl-open`
- **Then** the response SHALL display `+0.80` USDC

#### Scenario: Shows 0.00 when no open trades
- **Given** 0 open trades
- **When** the client requests `GET /api/panel/pnl-open`
- **Then** the response SHALL display `0.00` USDC

### Requirement: Historical PnL card

The system SHALL expose `GET /api/panel/pnl-historical` returning an HTML
fragment showing `SUM(CAST(pnl AS REAL))` of all
`paper_trades WHERE status='closed'`, formatted as a USDC string with 2
decimals (signed).

#### Scenario: Sums PnL of closed trades
- **Given** 2 closed trades with `pnl` = `1.50` and `-0.25`
- **When** the client requests `GET /api/panel/pnl-historical`
- **Then** the response SHALL display `+1.25` USDC

#### Scenario: Shows 0.00 when no closed trades
- **Given** 0 closed trades
- **When** the client requests `GET /api/panel/pnl-historical`
- **Then** the response SHALL display `0.00` USDC

### Requirement: Polling refresh every 5 seconds

The system SHALL configure HTMX on every panel element with
`hx-trigger="every 5s"` and a `hx-get` URL pointing at the matching
`/api/panel/*` route. The full page SHALL NOT reload during a poll.

#### Scenario: Panel HTML contains 5s trigger
- **Given** a running app
- **When** the client requests `GET /`
- **Then** the response SHALL contain the literal `every 5s` at least 7 times (one per panel)

### Requirement: Local Chart.js delivery

The system SHALL serve Chart.js 4.x from
`/static/vendor/chart.umd.min.js` (project-local file in
`src/copytrading/web/static/vendor/`). The index page SHALL reference
the asset by relative path. The system MUST NOT issue any network request
to a CDN at runtime.

#### Scenario: Static file served at vendor path
- **Given** a vendored `chart.umd.min.js` file under `static/vendor/`
- **When** the client requests `GET /static/vendor/chart.umd.min.js`
- **Then** the response SHALL be HTTP 200 with the file's bytes

#### Scenario: No CDN host in rendered HTML
- **Given** a running app
- **When** the client requests `GET /`
- **Then** the response body SHALL NOT contain any URL whose host is
  `cdn.jsdelivr.net`, `unpkg.com`, or `cdnjs.cloudflare.com`

### Requirement: Empty-state per panel

The system SHALL render a placeholder copy (e.g. "No data yet — waiting
for first snapshot") inside every panel that has no rows, instead of an
empty `<table>` or blank card.

#### Scenario: All panels with empty DB render placeholder
- **Given** a fresh empty database
- **When** the client requests any of the 7 panel endpoints
- **Then** the response SHALL contain the panel's empty-state placeholder text

### Requirement: Dark-mode visual style

The system SHALL serve a stylesheet at `/static/css/dashboard.css` that
defines a dark background palette, neon accent colors (cyan and violet),
monospace number formatting for all aggregate cards, and a
`backdrop-filter: blur(...)` rule for at least one glassmorphism surface.
The index page SHALL include a `<link rel="stylesheet" ...>` to that file
and a body class marker (e.g. `class="theme-dark"`) so a reviewer can
visually confirm the theme.

#### Scenario: Stylesheet is served and linked
- **Given** a running app with `static/css/dashboard.css` present
- **When** the client requests `GET /static/css/dashboard.css`
- **Then** the response SHALL be HTTP 200 with `text/css`
- **And** the body of `GET /` SHALL contain a `<link>` tag pointing to `/static/css/dashboard.css`

#### Scenario: CSS includes the neon + monospace markers
- **Given** a running app
- **When** the client requests `GET /static/css/dashboard.css`
- **Then** the response body SHALL contain the substring `font-family` followed by a monospace font name (e.g. `"JetBrains Mono"`, `"Fira Code"`, or `monospace`)
- **And** it SHALL contain at least one hex color matching the cyan or violet range (e.g. `#0ff`, `#0ea5e9`, `#8b5cf6`, `#a855f7`)

### Requirement: Local-only network access

The system SHALL bind to `127.0.0.1` by default. The startup command
documented in `README.md` SHALL NOT expose the dashboard on a public
interface for v1.

#### Scenario: Default bind address is loopback
- **Given** a default `uvicorn copytrading.web:app` invocation
- **When** the app starts
- **Then** it SHALL listen on `127.0.0.1` and not on `0.0.0.0`

### Requirement: Strict read-only behavior

The system MUST NOT expose any mutating HTTP route (`POST`, `PUT`,
`PATCH`, `DELETE`). All panel routes SHALL be `GET` and SHALL NOT call
any `Store` write method (`upsert_*`, `insert_*`, `update_*`).

#### Scenario: Mutating methods rejected
- **Given** a running app
- **When** the client requests `POST /`, `POST /api/panel/equity-curve`,
  or any other non-GET method on a panel path
- **Then** the response SHALL be HTTP 405 Method Not Allowed
