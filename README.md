# copytrading

Polymarket copy-trading bot: three cronjobs (leaderboard, copier, tracker) backed by SQLite and a Google Sheets sink, written in Python 3.13. The codebase is bootstrapped with `uv`; everything below assumes `uv` is installed.

## Canonical commands

```bash
# 1. Install / sync dependencies (creates .venv on first run)
uv sync

# 2. Lint
uv run ruff check .

# 3. Format
uv run ruff format .

# 4. Strict type-check
uv run mypy src tests

# 5. Run the test suite
uv run pytest
```

Copy `.env.example` to `.env` and fill in your Polymarket CLOB credentials and Google Sheets service-account path before running any cronjob.
