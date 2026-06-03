# Spec: config

## ADDED Requirements

### REQ-CONFIG-1: Environment Loading
`Settings.from_env()` SHALL load values from `.env` via `python-dotenv`.

#### Scenario: Load from .env file
- **Given** a `.env` file with `GOOGLE_SHEETS_CREDENTIALS_PATH=/path/creds.json` and `GOOGLE_SHEET_ID=abc123`
- **When** `Settings.from_env()` is called
- **Then** the returned `Settings` MUST have those values

### REQ-CONFIG-2: Fail Fast on Missing Keys
`Settings.from_env()` SHALL raise `ValueError` if any required key is missing.

#### Scenario: Missing GOOGLE_SHEET_ID
- **Given** a `.env` file with only `GOOGLE_SHEETS_CREDENTIALS_PATH`
- **When** `Settings.from_env()` is called
- **Then** a `ValueError` MUST be raised mentioning `GOOGLE_SHEET_ID`

### REQ-CONFIG-3: Typed Fields
`Settings` SHALL use `Path` for credentials path and `str` for sheet ID.

#### Scenario: Credentials path is a Path object
- **Given** valid environment variables
- **When** `Settings.from_env()` is called
- **Then** `settings.google_sheets_credentials_path` MUST be a `pathlib.Path`

### REQ-CONFIG-4: Exactly Two Keys
`Settings` SHALL require exactly 2 environment variables: `GOOGLE_SHEETS_CREDENTIALS_PATH` and `GOOGLE_SHEET_ID`.

#### Scenario: No Polymarket credentials needed
- **Given** a complete `.env` file
- **When** `Settings.from_env()` is called
- **Then** the `Settings` class MUST NOT reference any `POLY_*` variables
