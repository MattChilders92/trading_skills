#!/usr/bin/env python3
# ABOUTME: CLI wrapper for option chain data fetching.
# ABOUTME: Supports listing expiries, fetching chains by date, and a rich table display.

import argparse
import asyncio
import json
import sys

from trading_skills.options import get_expiries, get_option_chain


def _fmt(value, fmt=".2f", fallback="  —  "):
    """Format a numeric value or return a dash placeholder."""
    if value is None:
        return fallback
    return format(value, fmt)


def _print_chain_table(result: dict) -> None:
    """Render the option chain as a side-by-side calls | strike | puts table using Rich.

    Layout mirrors a standard broker options chain view:
      - Calls on the left (green when ITM)
      - Strike in the center (highlighted when near ATM)
      - Puts on the right (red when ITM)
    Rows are sorted by strike ascending.

    Args:
        result: Option chain dict with 'calls', 'puts', 'underlying_price', etc.
    """
    from rich import box
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text

    console = Console()
    symbol = result.get("symbol", "")
    expiry = result.get("expiry", "")
    spot = result.get("underlying_price")
    source = result.get("source", "yfinance")
    fetched = result.get("fetched_at", "")

    # Index puts by strike for O(1) lookup
    puts_by_strike = {r["strike"]: r for r in result.get("puts", [])}
    calls = result.get("calls", [])

    # Collect all unique strikes from both sides
    all_strikes = sorted(
        {r["strike"] for r in calls} | {r["strike"] for r in result.get("puts", [])}
    )

    title = f"[bold]{symbol}[/bold]  {expiry}  |  source: {source}"
    if spot:
        title += f"  |  spot: [bold yellow]${spot:.2f}[/bold yellow]"
    if fetched:
        title += f"  |  [dim]{fetched}[/dim]"

    table = Table(
        title=title,
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold white on grey23",
        border_style="grey50",
        min_width=90,
    )

    # Calls side (left)
    table.add_column("Δ Delta",  justify="right",  style="cyan",       width=7)
    table.add_column("Θ Theta",  justify="right",  style="magenta",    width=7)
    table.add_column("OI",       justify="right",  style="dim",        width=7)
    table.add_column("Bid",      justify="right",  width=7)
    table.add_column("Ask",      justify="right",  width=7)
    table.add_column("Mid",      justify="right",  style="bold",       width=7)
    # Center
    table.add_column("STRIKE",   justify="center", style="bold white", width=9)
    # Puts side (right)
    table.add_column("Mid",      justify="left",   style="bold",       width=7)
    table.add_column("Bid",      justify="left",   width=7)
    table.add_column("Ask",      justify="left",   width=7)
    table.add_column("OI",       justify="left",   style="dim",        width=7)
    table.add_column("Θ Theta",  justify="left",   style="magenta",    width=7)
    table.add_column("Δ Delta",  justify="left",   style="cyan",       width=7)

    calls_by_strike = {r["strike"]: r for r in calls}

    for strike in all_strikes:
        call = calls_by_strike.get(strike)
        put = puts_by_strike.get(strike)

        # Determine if ATM (within 2% of spot)
        is_atm = spot is not None and abs(strike - spot) / spot < 0.02
        strike_style = "bold yellow" if is_atm else "white"
        strike_text = Text(f"${strike:.1f}", style=strike_style, justify="center")

        # Call is ITM when strike < spot
        call_itm = spot is not None and strike < spot
        # Put is ITM when strike > spot
        put_itm = spot is not None and strike > spot

        def call_cell(val, fmt=".2f"):
            text = Text(_fmt(val, fmt), justify="right")
            if call_itm and val is not None:
                text.stylize("green")
            return text

        def put_cell(val, fmt=".2f"):
            text = Text(_fmt(val, fmt), justify="left")
            if put_itm and val is not None:
                text.stylize("red")
            return text

        c_delta = call_cell(call.get("delta") if call else None, ".2f")
        c_theta = call_cell(call.get("theta") if call else None, ".2f")
        c_oi    = call_cell(call.get("openInterest") if call else None, ",.0f")
        c_bid   = call_cell(call.get("bid") if call else None)
        c_ask   = call_cell(call.get("ask") if call else None)
        c_mid   = call_cell(call.get("lastPrice") if call else None)

        p_mid   = put_cell(put.get("lastPrice") if put else None)
        p_bid   = put_cell(put.get("bid") if put else None)
        p_ask   = put_cell(put.get("ask") if put else None)
        p_oi    = put_cell(put.get("openInterest") if put else None, ",.0f")
        p_theta = put_cell(put.get("theta") if put else None, ".2f")
        p_delta = put_cell(put.get("delta") if put else None, ".2f")

        row_style = "on grey11" if is_atm else ""
        table.add_row(
            c_delta, c_theta, c_oi, c_bid, c_ask, c_mid,
            strike_text,
            p_mid, p_bid, p_ask, p_oi, p_theta, p_delta,
            style=row_style,
        )

    console.print()
    console.print(table)
    console.print(
        "  [dim]CALLS (green=ITM)[/dim]"
        "  [cyan]Δ=delta[/cyan]  [magenta]Θ=theta/day[/magenta]"
        f"{'':>20}"
        "[dim]PUTS (red=ITM)[/dim]"
    )
    console.print()


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
    parser.add_argument(
        "--strikes-above",
        type=int,
        default=10,
        help="Tastytrade: OTM call strikes to include above spot price (default 10)",
    )
    parser.add_argument(
        "--strikes-below",
        type=int,
        default=10,
        help="Tastytrade: OTM put strikes to include below spot price (default 10)",
    )
    parser.add_argument(
        "--table",
        action="store_true",
        help="Print a colored side-by-side options chain table instead of JSON",
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

            result = asyncio.run(
                get_option_chain_tastytrade(
                    symbol,
                    args.expiry,
                    strikes_above=args.strikes_above,
                    strikes_below=args.strikes_below,
                )
            )
        else:
            result = get_option_chain(symbol, args.expiry)

        if "error" in result:
            print(json.dumps(result, indent=2))
            sys.exit(1)

        if args.table:
            _print_chain_table(result)
        else:
            print(json.dumps(result, indent=2))
    else:
        # Default: show expiries
        expiries = get_expiries(symbol)
        if not expiries:
            print(json.dumps({"error": f"No options found for {symbol}"}))
            sys.exit(1)
        print(json.dumps({"symbol": symbol, "expiries": expiries}, indent=2))


if __name__ == "__main__":
    main()
