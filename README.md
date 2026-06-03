# copytrading

Paper copy-trading bot for Polymarket: three cronjobs (leaderboard discovery, position copier, account tracker) backed by SQLite and Google Sheets, written in Python 3.13.

**Paper trading only** — no real trades are executed. The bot reads public Polymarket data and simulates copy trades locally.

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure Google Sheets OAuth2

The bot uses OAuth2 (not service account) to access Google Sheets.

1. Copy `.env.example` to `.env`
2. Set `GOOGLE_SHEETS_CREDENTIALS_PATH` to your OAuth2 client secret JSON file
3. Set `GOOGLE_SHEET_ID` to your spreadsheet ID (from the URL)

Example `.env`:
```bash
GOOGLE_SHEETS_CREDENTIALS_PATH=/path/to/client_secret.json
GOOGLE_SHEET_ID=1NKYMZXTPaR41sEtxzbs3i_igPh6BXNH9GBEKX9OOWAI
```

On first run, the bot will open a browser for OAuth2 consent. Tokens are cached in `.google_token.json`.

### 3. Create Google Sheets tabs

Your spreadsheet needs three tabs:
- **leaderboard** — top wallets (Rank, Address, Total PnL, Last Checked)
- **history** — paper trades (Timestamp, Wallet, Market, Side, Size, Entry, Exit, Status, PnL, Closed)
- **account** — equity snapshots (Timestamp, Equity, Open Trades, Total PnL)

## Running cronjobs

```bash
# Discover top wallets and update leaderboard
uv run python -m copytrading.cronjobs.leaderboard_discovery

# Copy positions as paper trades (0.5% risk per trade)
uv run python -m copytrading.cronjobs.position_copier

# Track account equity and update account sheet
uv run python -m copytrading.cronjobs.account_tracker
```

### Recommended cron schedule

```cron
# Every 5 minutes: discover new wallets
*/5 * * * * cd /path/to/copytrading && uv run python -m copytrading.cronjobs.leaderboard_discovery

# Every minute: copy positions
* * * * * cd /path/to/copytrading && uv run python -m copytrading.cronjobs.position_copier

# Every 15 minutes: track account
*/15 * * * * cd /path/to/copytrading && uv run python -m copytrading.cronjobs.account_tracker
```

## Development

```bash
# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type-check
uv run mypy src tests

# Run tests
uv run pytest
```

## Architecture

```
src/copytrading/
├── config.py           # Settings from .env
├── models.py           # Dataclasses (Wallet, Position, PaperTrade, etc.)
├── store.py            # SQLite repository
├── poly_client.py      # Read-only Polymarket API client (httpx)
├── sheets_client.py    # Google Sheets OAuth2 client
├── risk.py             # Position sizing (0.5% risk)
└── cronjobs/
    ├── leaderboard_discovery.py
    ├── position_copier.py
    └── account_tracker.py
```

## Risk management

- **Position size**: 0.5% of current equity per trade
- **Starting equity**: 200 USDC (paper balance)
- **Decimal math**: All calculations use `Decimal` for precision

## License

Private — not for redistribution.
