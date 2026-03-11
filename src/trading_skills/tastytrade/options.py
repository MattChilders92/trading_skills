# ABOUTME: Fetches real-time option chain data from Tastytrade.
# ABOUTME: Output shape matches the yfinance option chain format for drop-in compatibility.

import asyncio
import bisect
from datetime import date, datetime, timezone
from decimal import Decimal

from tastytrade import DXLinkStreamer
from tastytrade.dxfeed import Greeks, Quote, Summary
from tastytrade.instruments import Option, OptionType, get_option_chain

from trading_skills.tastytrade.connection import tastytrade_session

# Seconds to wait for quote events before returning with whatever was received.
_STREAM_TIMEOUT = 10


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


def _atm_slice(
    options: list[Option],
    underlying_price: float,
    strikes_above: int,
    strikes_below: int,
) -> tuple[list[Option], list[Option]]:
    """Select call and put options within N strikes of the current price.

    Args:
        options: All option contracts for this expiration.
        underlying_price: Current underlying spot price.
        strikes_above: Number of OTM call strikes to include above spot.
        strikes_below: Number of OTM put strikes to include below spot.

    Returns:
        Tuple of (filtered_calls, filtered_puts) sorted by strike ascending.
    """
    calls = sorted(
        [o for o in options if o.option_type == OptionType.CALL],
        key=lambda o: float(o.strike_price),
    )
    puts = sorted(
        [o for o in options if o.option_type == OptionType.PUT],
        key=lambda o: float(o.strike_price),
    )
    call_prices = [float(o.strike_price) for o in calls]
    put_prices = [float(o.strike_price) for o in puts]

    # bisect gives first index >= price (first OTM call / first ITM put)
    c_idx = bisect.bisect_left(call_prices, underlying_price)
    p_idx = bisect.bisect_left(put_prices, underlying_price)

    filtered_calls = calls[max(0, c_idx - strikes_below) : c_idx + strikes_above]
    filtered_puts = puts[max(0, p_idx - strikes_below) : p_idx + strikes_above]
    return filtered_calls, filtered_puts


async def _get_underlying_price(session, symbol: str) -> float | None:
    """Fetch current underlying mid-price via a short DXLink stream.

    Opens a dedicated streamer subscription for just the equity symbol,
    waits up to 3 seconds for the first quote, then returns.

    Args:
        session: Authenticated Tastytrade session.
        symbol: Equity ticker (e.g. 'BA').

    Returns:
        Mid-price float or None if unavailable.
    """
    try:
        async with DXLinkStreamer(session) as streamer:
            await streamer.subscribe(Quote, [symbol])
            q = await asyncio.wait_for(streamer.get_event(Quote), timeout=3.0)
            if q.bid_price is not None and q.ask_price is not None:
                return float((q.bid_price + q.ask_price) / 2)
    except Exception:
        pass
    return None


async def _stream_option_quotes(
    session,
    options: list[Option],
) -> tuple[dict[str, Quote], dict[str, Summary], dict[str, Greeks]]:
    """Stream Quote, Summary, and Greeks events for a set of options via DXLink WebSocket.

    Collects all three event types concurrently until every symbol has received at
    least one of each, or the timeout expires.

    Args:
        session: Authenticated Tastytrade session.
        options: Option contracts to stream data for.

    Returns:
        Tuple of (quotes, summaries, greeks) each mapping streamer_symbol → event.
    """
    syms = [o.streamer_symbol for o in options if o.streamer_symbol]
    if not syms:
        return {}, {}, {}

    quotes: dict[str, Quote] = {}
    summaries: dict[str, Summary] = {}
    greeks_map: dict[str, Greeks] = {}
    need_q = set(syms)
    need_s = set(syms)
    need_g = set(syms)

    async with DXLinkStreamer(session) as streamer:
        await streamer.subscribe(Quote, syms)
        await streamer.subscribe(Summary, syms)
        await streamer.subscribe(Greeks, syms)

        deadline = asyncio.get_event_loop().time() + _STREAM_TIMEOUT

        async def _collect(event_cls, store, needed):
            while needed:
                rem = deadline - asyncio.get_event_loop().time()
                if rem <= 0:
                    break
                try:
                    ev = await asyncio.wait_for(
                        streamer.get_event(event_cls), timeout=min(1.0, rem)
                    )
                    if ev.event_symbol in needed:
                        store[ev.event_symbol] = ev
                        needed.discard(ev.event_symbol)
                except asyncio.TimeoutError:
                    break

        await asyncio.gather(
            _collect(Quote, quotes, need_q),
            _collect(Summary, summaries, need_s),
            _collect(Greeks, greeks_map, need_g),
        )

    return quotes, summaries, greeks_map


def _build_option_record(
    opt: Option,
    quotes: dict[str, Quote],
    summaries: dict[str, Summary],
    greeks_map: dict[str, Greeks],
) -> dict:
    """Build a single option record matching the yfinance output schema.

    Args:
        opt: Option instrument object from Tastytrade.
        quotes: Dict mapping streamer_symbol → Quote event.
        summaries: Dict mapping streamer_symbol → Summary event.
        greeks_map: Dict mapping streamer_symbol → Greeks event.

    Returns:
        Dict with strike, bid, ask, lastPrice, volume, openInterest, impliedVolatility,
        delta, theta, gamma, vega, inTheMoney fields.
    """
    sym = opt.streamer_symbol
    q = quotes.get(sym)
    s = summaries.get(sym)
    g = greeks_map.get(sym)

    bid = q.bid_price if q and q.bid_price is not None else None
    ask = q.ask_price if q and q.ask_price is not None else None
    mid = _decimal_to_float((bid + ask) / 2) if bid is not None and ask is not None else None

    return {
        "strike": float(opt.strike_price),
        "bid": _decimal_to_float(bid),
        "ask": _decimal_to_float(ask),
        "lastPrice": mid,
        "volume": None,  # intraday volume not in Summary; use Trade event if needed
        "openInterest": s.open_interest if s else None,
        "impliedVolatility": _decimal_to_float(g.volatility, 4) if g else None,
        "delta": _decimal_to_float(g.delta, 4) if g else None,
        "theta": _decimal_to_float(g.theta, 4) if g else None,
        "gamma": _decimal_to_float(g.gamma, 4) if g else None,
        "vega": _decimal_to_float(g.vega, 4) if g else None,
        "inTheMoney": bid is not None and bid > Decimal(0),
    }


async def get_option_chain_tastytrade(
    symbol: str,
    expiry: str,
    strikes_above: int = 10,
    strikes_below: int = 10,
) -> dict:
    """Fetch real-time option chain from Tastytrade for a specific expiration date.

    Uses DXLink WebSocket streaming (works with standard accounts — no premium
    REST data subscription required). Filters to ATM ± N strikes to keep output
    focused and streaming fast.

    Args:
        symbol: Underlying ticker symbol (e.g. 'BA', 'SPY').
        expiry: Expiration date in YYYY-MM-DD format.
        strikes_above: Number of strikes above current price to include (default 10).
        strikes_below: Number of strikes below current price to include (default 10).

    Returns:
        Dict with keys: symbol, source, fetched_at, expiry, underlying_price, calls, puts.
        On error returns dict with 'error' key.
    """
    target_date = _parse_expiry(expiry)

    try:
        async with tastytrade_session() as session:
            # 1. Fetch option chain contract definitions (no pricing)
            chain_by_date = await get_option_chain(session, symbol.upper())

            if target_date not in chain_by_date:
                available = sorted(chain_by_date.keys())
                return {
                    "error": (
                        f"No options found for {symbol} expiring {expiry}. "
                        f"Available: {[str(d) for d in available[:10]]}"
                    )
                }

            all_options: list[Option] = chain_by_date[target_date]

            # 2. Get underlying price to anchor the strike filter
            underlying_price = await _get_underlying_price(session, symbol.upper())

            # 3. Filter to ATM ± N strikes; fall back to all options if no price
            if underlying_price is not None:
                calls, puts = _atm_slice(
                    all_options, underlying_price, strikes_above, strikes_below
                )
            else:
                calls = [o for o in all_options if o.option_type == OptionType.CALL]
                puts = [o for o in all_options if o.option_type == OptionType.PUT]

            # 4. Stream quotes for only the filtered strikes (~20 symbols vs 130+)
            quotes, summaries, greeks_map = await _stream_option_quotes(session, calls + puts)

            def _quoted_records(opts: list[Option]) -> list[dict]:
                """Return records for options that received at least a bid or ask."""
                records = [_build_option_record(o, quotes, summaries, greeks_map) for o in opts]
                return [r for r in records if r["bid"] is not None or r["ask"] is not None]

            return {
                "symbol": symbol.upper(),
                "source": "tastytrade",
                "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "expiry": expiry,
                "underlying_price": underlying_price,
                "calls": _quoted_records(calls),
                "puts": _quoted_records(puts),
            }

    except EnvironmentError as e:
        return {"error": str(e)}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": f"Tastytrade API error: {e}"}
