# ABOUTME: Fetches real-time option chain data from Tastytrade.
# ABOUTME: Output shape matches the yfinance option chain format for drop-in compatibility.

from datetime import date, datetime, timezone
from decimal import Decimal

from tastytrade.instruments import Option, OptionType, get_option_chain
from tastytrade.market_data import get_market_data_by_type

from trading_skills.tastytrade.connection import tastytrade_session


def _parse_expiry(expiry: str) -> date:
    """Parse expiry string YYYY-MM-DD into a date object.

    Args:
        expiry: Expiration date string in YYYY-MM-DD format.

    Returns:
        Parsed date object.

    Raises:
        ValueError: If the format is invalid.
    """
    try:
        return datetime.strptime(expiry, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Invalid expiry format '{expiry}'. Expected YYYY-MM-DD.")


def _decimal_to_float(value: Decimal | None, decimals: int = 2) -> float | None:
    """Convert Decimal to rounded float, returning None for missing values.

    Args:
        value: Decimal value or None.
        decimals: Number of decimal places to round to.

    Returns:
        Rounded float or None.
    """
    if value is None:
        return None
    return round(float(value), decimals)


def _build_option_record(opt: Option, market_data_map: dict) -> dict:
    """Build a single option record matching the yfinance output schema.

    Args:
        opt: Option instrument object from Tastytrade.
        market_data_map: Dict mapping OCC symbol → MarketData object.

    Returns:
        Dict with strike, bid, ask, lastPrice, volume, openInterest, impliedVolatility,
        inTheMoney fields.
    """
    md = market_data_map.get(opt.symbol)
    return {
        "strike": float(opt.strike_price),
        "bid": _decimal_to_float(md.bid if md else None),
        "ask": _decimal_to_float(md.ask if md else None),
        "lastPrice": _decimal_to_float(md.mark if md else None),
        "volume": int(md.volume) if md and md.volume is not None else None,
        "openInterest": int(md.open_interest) if md and md.open_interest is not None else None,
        "impliedVolatility": None,  # requires DXLink streamer; use greeks skill for IV
        "inTheMoney": md.bid is not None and md.bid > Decimal(0) if md else False,
    }


async def get_option_chain_tastytrade(symbol: str, expiry: str) -> dict:
    """Fetch real-time option chain from Tastytrade for a specific expiration date.

    Output shape is identical to the yfinance option chain format so that callers
    can switch sources transparently.

    Args:
        symbol: Underlying ticker symbol (e.g. 'BA', 'SPY').
        expiry: Expiration date in YYYY-MM-DD format.

    Returns:
        Dict with keys: symbol, source, fetched_at, expiry, underlying_price, calls, puts.
        On error returns dict with 'error' key.
    """
    target_date = _parse_expiry(expiry)

    try:
        async with tastytrade_session() as session:
            # Get full option chain (all expirations, returns dict[date, list[Option]])
            chain_by_date = await get_option_chain(session, symbol.upper())

            if target_date not in chain_by_date:
                available = sorted(chain_by_date.keys())
                return {
                    "error": (
                        f"No options found for {symbol} expiring {expiry}. "
                        f"Available: {[str(d) for d in available[:10]]}"
                    )
                }

            options: list[Option] = chain_by_date[target_date]
            calls = [o for o in options if o.option_type == OptionType.CALL]
            puts = [o for o in options if o.option_type == OptionType.PUT]

            # Fetch market data (bid/ask/mark/volume/OI) via REST — up to 100 per call
            all_symbols = [o.symbol for o in options]
            market_data_list = await get_market_data_by_type(session, options=all_symbols)
            market_data_map = {md.symbol: md for md in market_data_list}

            # Get underlying price from equity market data
            equity_data = await get_market_data_by_type(
                session, equities=[symbol.upper()]
            )
            underlying_price = (
                _decimal_to_float(equity_data[0].mark) if equity_data else None
            )

            return {
                "symbol": symbol.upper(),
                "source": "tastytrade",
                "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "expiry": expiry,
                "underlying_price": underlying_price,
                "calls": sorted(
                    [_build_option_record(o, market_data_map) for o in calls],
                    key=lambda r: r["strike"],
                ),
                "puts": sorted(
                    [_build_option_record(o, market_data_map) for o in puts],
                    key=lambda r: r["strike"],
                ),
            }

    except EnvironmentError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Tastytrade API error: {e}"}
