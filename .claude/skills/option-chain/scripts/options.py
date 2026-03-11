#!/usr/bin/env python3
# ABOUTME: CLI wrapper for option chain data fetching.
# ABOUTME: Supports listing expiries and fetching chains by date.

import argparse
import asyncio
import json
import sys

from trading_skills.options import get_expiries, get_option_chain


def main():
    parser = argparse.ArgumentParser(description="Fetch option chain data")
    parser.add_argument("symbol", help="Ticker symbol")
    parser.add_argument("--expiries", action="store_true", help="List expiration dates only")
    parser.add_argument("--expiry", help="Fetch chain for specific expiry (YYYY-MM-DD)")
    parser.add_argument(
        "--source",
        choices=["yfinance", "tastytrade"],
        default="yfinance",
        help="Data source: yfinance (delayed, default) or tastytrade (real-time)",
    )

    args = parser.parse_args()
    symbol = args.symbol.upper()

    if args.expiries:
        expiries = get_expiries(symbol)
        if not expiries:
            print(json.dumps({"error": f"No options found for {symbol}"}))
            sys.exit(1)
        print(json.dumps({"symbol": symbol, "expiries": expiries}, indent=2))
    elif args.expiry:
        if args.source == "tastytrade":
            from trading_skills.tastytrade.options import get_option_chain_tastytrade

            result = asyncio.run(get_option_chain_tastytrade(symbol, args.expiry))
        else:
            result = get_option_chain(symbol, args.expiry)
        print(json.dumps(result, indent=2))
        if "error" in result:
            sys.exit(1)
    else:
        # Default: show expiries (yfinance only)
        expiries = get_expiries(symbol)
        if not expiries:
            print(json.dumps({"error": f"No options found for {symbol}"}))
            sys.exit(1)
        print(json.dumps({"symbol": symbol, "expiries": expiries}, indent=2))


if __name__ == "__main__":
    main()
