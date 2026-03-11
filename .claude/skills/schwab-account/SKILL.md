---
name: schwab-account
description: Get account summary from Charles Schwab including cash balance, buying power, and net liquidation value. Use when user asks about their Schwab account, balance, buying power, or available cash. Requires SCHWAB_API_KEY, SCHWAB_APP_SECRET, and a saved token file.
dependencies: ["trading-skills", "schwab-py"]
---

# Schwab Account

Fetch account summary from Charles Schwab (read-only).

## Prerequisites

You need a Charles Schwab brokerage account and a registered app in the
[Schwab Developer Portal](https://developer.schwab.com/).

### One-time setup

1. Log in to [developer.schwab.com](https://developer.schwab.com/) and create an app
2. Note your **API Key** and **App Secret**
3. Set environment variables:

```bash
export SCHWAB_API_KEY="your-api-key"
export SCHWAB_APP_SECRET="your-app-secret"
# Optional: override default token path (~/.schwab_token.json)
export SCHWAB_TOKEN_PATH="/path/to/schwab_token.json"
```

4. Run the one-time browser authentication to save your token:

```bash
uv run python -c "
from trading_skills.broker.schwab.connection import first_time_setup
first_time_setup()
"
```

This opens a browser window. Log in, approve access, and the token is saved automatically.
After this, `SCHWAB_API_KEY` and `SCHWAB_APP_SECRET` are all that's needed going forward.

## Instructions

> **Note:** If `uv` is not installed or `pyproject.toml` is not found, replace `uv run python` with `python` in all commands below.

```bash
uv run python scripts/account.py [--account HASH] [--all-accounts]
```

**Default behavior** (no flags): fetches the first linked account.
**Use `--all-accounts`** when user has multiple accounts or asks for a full overview.

## Arguments

- `--account HASH` - Specific account hash to fetch (from Schwab API, not account number)
- `--all-accounts` - Fetch summaries for all linked accounts

## Output

Returns JSON with:
- `connected` - Whether the API call succeeded
- `accounts` - List of account summaries, each with:
  - `account` - Account number
  - `summary` - `net_liquidation`, `total_cash`, `buying_power`, `available_funds`,
    `maintenance_margin`, `unrealized_pnl`
  - `currency` - Always `"USD"`

If not connected, explain the setup steps above.

## Dependencies

- `schwab-py`
