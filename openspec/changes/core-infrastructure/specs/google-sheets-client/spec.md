# Spec: google-sheets-client

## ADDED Requirements

### REQ-SHEETS-1: Service Account Auth
`SheetsClient` SHALL authenticate using a Google service account JSON file.

#### Scenario: Load credentials from file
- **Given** a valid service account JSON file path
- **When** `SheetsClient.from_settings(settings)` is called
- **Then** the client MUST be authenticated and ready to make API calls

### REQ-SHEETS-2: update_leaderboard
`update_leaderboard(wallets)` SHALL write wallet data to the "leaderboard" sheet.

#### Scenario: Write top 20 wallets
- **Given** a list of 20 `Wallet` objects
- **When** `update_leaderboard(wallets)` is called
- **Then** the "leaderboard" sheet MUST contain those wallets with rank, address, and PnL

### REQ-SHEETS-3: append_trades
`append_trades(trades)` SHALL append paper trades to the "history" sheet.

#### Scenario: Record new paper trades
- **Given** a list of `PaperTrade` objects
- **When** `append_trades(trades)` is called
- **Then** the "history" sheet MUST have new rows for each trade

### REQ-SHEETS-4: update_account
`update_account(snapshot)` SHALL write account summary to the "account" sheet.

#### Scenario: Update account equity
- **Given** an `AccountSnapshot` with current equity
- **When** `update_account(snapshot)` is called
- **Then** the "account" sheet MUST reflect the current balance

### REQ-SHEETS-5: Error Handling
All methods SHALL raise `SheetsClientError` on API failures.

#### Scenario: API quota exceeded
- **Given** the Sheets API returns a 429 status
- **When** any write method is called
- **Then** `SheetsClientError` MUST be raised
