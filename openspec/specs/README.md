# Specs — copytrading

This directory holds the **main specs** (source of truth) for the copytrading
project. Delta specs produced by `sdd-spec` for each change live under
`openspec/changes/{change-name}/specs/{domain}/spec.md` until they are
synced here by `sdd-archive`.

## Domains (proposed)

| Domain | Owner | Scope |
| --- | --- | --- |
| `leaderboard` | leaderboard_discovery script | Top-N wallet selection + Google Sheet write |
| `positions`   | position_copier script       | Copy trading loop, sizing, order execution |
| `accounting`  | account_tracker script       | History, P&L, account movements to Google Sheet |
| `risk`        | cross-cutting                | 0.5% risk cap, starting balance 200 USDC |
| `storage`     | cross-cutting                | SQLite schema and access patterns |

These domain names are placeholders. The first `sdd-spec` change should
either adopt them or rename them based on the actual change scope.
