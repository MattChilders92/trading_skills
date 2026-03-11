#!/usr/bin/env python3
# ABOUTME: CLI wrapper for Schwab account summary fetching.
# ABOUTME: Requires SCHWAB_API_KEY, SCHWAB_APP_SECRET, and a saved token file.

import argparse
import json
import sys

from trading_skills.broker.schwab.account import get_account_summary


def main():
    parser = argparse.ArgumentParser(description="Fetch account summary from Charles Schwab")
    parser.add_argument("--account", help="Specific account hash to fetch")
    parser.add_argument(
        "--all-accounts", action="store_true", help="Fetch all linked accounts"
    )

    args = parser.parse_args()
    result = get_account_summary(
        account_hash=args.account,
        all_accounts=args.all_accounts,
    )
    print(json.dumps(result, indent=2))
    if not result.get("connected"):
        sys.exit(1)


if __name__ == "__main__":
    main()
