---
name: option-chain
description: Get option chain data including calls and puts with strikes, bids, asks, volume, open interest, and implied volatility. Use when user asks about options, option prices, calls, puts, or option chain for a specific expiration date.
dependencies: ["trading-skills"]
---

# Option Chain

Fetch option chain data for a specific expiration date. Supports two data sources:
- `yfinance` (default) — free, ~15 min delayed
- `tastytrade` — real-time, requires `TT_SECRET` and `TT_REFRESH` env vars

## Instructions

> **Note:** If `uv` is not installed or `pyproject.toml` is not found, replace `uv run python` with `python` in all commands below.

First, get available expiration dates (yfinance only):
```bash
uv run python scripts/options.py SYMBOL --expiries
```

Fetch the chain (delayed, default):
```bash
uv run python scripts/options.py SYMBOL --expiry YYYY-MM-DD
```

Fetch the chain with real-time pricing via Tastytrade:
```bash
uv run python scripts/options.py SYMBOL --expiry YYYY-MM-DD --source tastytrade
```

## Arguments

- `SYMBOL` - Ticker symbol (e.g., AAPL, SPY, TSLA)
- `--expiries` - List available expiration dates only (yfinance source)
- `--expiry YYYY-MM-DD` - Fetch chain for specific date
- `--source yfinance|tastytrade` - Data source (default: `yfinance`)

## Output

Returns JSON with:
- `source` - Data source used (`yfinance` or `tastytrade`)
- `fetched_at` - UTC timestamp of data fetch
- `calls` / `puts` - Array of option records with strike, bid, ask, lastPrice, volume,
  openInterest, impliedVolatility
- `underlying_price` - Current stock price for reference

Always show the `fetched_at` timestamp so the user knows data freshness.
Present data as a table. Highlight high volume/OI strikes and notable IV levels.

## Dependencies

- `pandas`
- `yfinance`
- `tastytrade` (for `--source tastytrade`)
