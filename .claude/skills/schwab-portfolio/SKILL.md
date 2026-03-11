---
name: schwab-portfolio
description: Get portfolio positions from Charles Schwab including stocks and options with market values, P&L, and option details. Use when user asks about their Schwab portfolio, positions, holdings, or what stocks/options they own. Requires SCHWAB_API_KEY, SCHWAB_APP_SECRET, and a saved token file.
dependencies: ["trading-skills", "schwab-py"]
---

# Schwab Portfolio

Fetch portfolio positions from Charles Schwab (read-only). Output format matches the
IB portfolio schema so downstream analysis tools work interchangeably.

## Prerequisites

See the `schwab-account` skill for one-time setup instructions (env vars + browser auth).

## Instructions

> **Note:** If `uv` is not installed or `pyproject.toml` is not found, replace `uv run python` with `python` in all commands below.

```bash
uv run python scripts/portfolio.py [--account HASH] [--all-accounts]
```

**Default behavior** (no flags): fetches positions for the first linked account.

## Arguments

- `--account HASH` - Specific account hash (use hash from API, not account number)
- `--all-accounts` - Fetch positions across all linked accounts

## Output

Returns JSON with:
- `connected` - Whether the API call succeeded
- `accounts` - List of account numbers included
- `position_count` - Total number of positions
- `positions` - Array of position objects, each with:
  - `account` - Account number
  - `symbol` - Underlying ticker (e.g. `BA`)
  - `sec_type` - `STK` or `OPT`
  - `quantity` - Signed quantity (negative = short)
  - `avg_cost` - Average cost per share/contract
  - `market_price` - Current market price
  - `market_value` - Total market value
  - `unrealized_pnl` - Unrealized profit/loss
  - `strike`, `expiry` (YYYYMMDD), `right` (`C`/`P`) - Options only, null for equities
  - `underlying_price` - Always null (use `stock-quote` skill to fetch)

If not connected, explain the setup steps in the `schwab-account` skill.

## Dependencies

- `schwab-py`
