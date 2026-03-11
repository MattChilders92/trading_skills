---
name: tastytrade-option-chain
description: Get real-time option chain data from Tastytrade including calls and puts with strikes, bids, asks, volume, and open interest. Use when user asks for real-time or up-to-date options pricing via Tastytrade. Requires TT_SECRET and TT_REFRESH environment variables.
dependencies: ["trading-skills", "tastytrade"]
---

# Tastytrade Option Chain

Fetch real-time option chain data from Tastytrade. Output format is identical to the
`option-chain` skill (yfinance) so results can be used interchangeably.

## Prerequisites

You need a Tastytrade brokerage account (unfunded accounts are supported) and OAuth2
credentials from the [Tastytrade developer portal](https://developer.tastytrade.com/).

### One-time setup

1. Log in to [developer.tastytrade.com](https://developer.tastytrade.com/) and create an app
2. Copy your **Provider Secret** (`TT_SECRET`) and generate a **Refresh Token** (`TT_REFRESH`)
3. Set environment variables:

```bash
export TT_SECRET="your-provider-secret"
export TT_REFRESH="your-refresh-token"
```

> The refresh token expires after a period of inactivity. If you get an auth error,
> regenerate it from the developer portal.

## Instructions

> **Note:** If `uv` is not installed or `pyproject.toml` is not found, replace `uv run python` with `python` in all commands below.

```bash
uv run python scripts/options.py SYMBOL --expiry YYYY-MM-DD
```

## Arguments

- `SYMBOL` - Ticker symbol (e.g., BA, SPY, AAPL)
- `--expiry YYYY-MM-DD` - Expiration date to fetch (required)

## Output

Returns JSON with:
- `symbol` - Ticker symbol
- `source` - `"tastytrade"`
- `fetched_at` - UTC timestamp of when data was fetched
- `expiry` - Expiration date
- `underlying_price` - Current stock price (mark price)
- `calls` / `puts` - Array of option records, each with:
  - `strike`, `bid`, `ask`, `lastPrice` (mark), `volume`, `openInterest`
  - `impliedVolatility` is `null` — use the `greeks` skill for IV calculation

Present data as a table. Note the `fetched_at` timestamp so the user can see data freshness.
For IV and Greeks on a specific contract, pipe the bid/ask into the `greeks` skill.

## Examples

```bash
# BA calls and puts expiring March 2026
uv run python scripts/options.py BA --expiry 2026-03-20

# SPY options for next monthly expiry
uv run python scripts/options.py SPY --expiry 2026-04-17
```

## Dependencies

- `tastytrade`
