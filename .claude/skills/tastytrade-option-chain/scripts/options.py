#!/usr/bin/env python3
# ABOUTME: CLI wrapper for Tastytrade real-time option chain fetching.
# ABOUTME: Requires TT_SECRET and TT_REFRESH environment variables.

import argparse
import asyncio
import json
import sys

from trading_skills.tastytrade.options import get_option_chain_tastytrade


def main():
    parser = argparse.ArgumentParser(
        description="Fetch real-time option chain data from Tastytrade"
    )
    parser.add_argument("symbol", help="Ticker symbol (e.g. BA, SPY)")
    parser.add_argument(
        "--expiry", required=True, help="Expiration date in YYYY-MM-DD format"
    )

    args = parser.parse_args()
    result = asyncio.run(
        get_option_chain_tastytrade(args.symbol.upper(), args.expiry)
    )
    print(json.dumps(result, indent=2))
    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
