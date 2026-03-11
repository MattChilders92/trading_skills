# ABOUTME: Fetches portfolio positions from Charles Schwab (read-only).
# ABOUTME: Output shape mirrors the IB portfolio schema for drop-in compatibility.

from schwab.client import Client

from trading_skills.broker.schwab.connection import get_client


def _parse_position(pos: dict, account_number: str) -> dict:
    """Parse a single position from the Schwab API response.

    Maps Schwab instrument types and fields to the shared portfolio position schema
    used by the IB integration for consistency.

    Args:
        pos: Position dict from the Schwab positions list.
        account_number: Account number this position belongs to.

    Returns:
        Normalized position dict.
    """
    instrument = pos.get("instrument", {})
    asset_type = instrument.get("assetType", "EQUITY")

    quantity = pos.get("longQuantity", 0) - pos.get("shortQuantity", 0)
    is_short = pos.get("shortQuantity", 0) > 0

    # Normalize asset type to match IB schema (STK / OPT)
    sec_type = "OPT" if asset_type == "OPTION" else "STK"

    result = {
        "account": account_number,
        "symbol": instrument.get("underlyingSymbol") or instrument.get("symbol", ""),
        "sec_type": sec_type,
        "currency": "USD",
        "quantity": -pos.get("shortQuantity", 0) if is_short else pos.get("longQuantity", 0),
        "avg_cost": pos.get("averagePrice"),
        "market_price": pos.get("marketValue") / abs(quantity) if quantity else None,
        "market_value": pos.get("marketValue"),
        "unrealized_pnl": pos.get("longOpenProfitLoss") or pos.get("shortOpenProfitLoss"),
        # Option-specific fields (null for equities)
        "strike": None,
        "expiry": None,
        "right": None,
        "underlying_price": None,
    }

    if sec_type == "OPT":
        result["strike"] = instrument.get("strikePrice")
        expiry_raw = instrument.get("expirationDate", "")
        # Normalize from ISO datetime string to YYYYMMDD
        result["expiry"] = expiry_raw[:10].replace("-", "") if expiry_raw else None
        put_call = instrument.get("putCall", "")
        result["right"] = "C" if put_call.upper() == "CALL" else "P"

    return result


def get_portfolio(account_hash: str | None = None, all_accounts: bool = False) -> dict:
    """Fetch portfolio positions from Charles Schwab.

    Args:
        account_hash: Specific account hash to fetch. If not provided, uses first account.
        all_accounts: If True, fetch positions for all linked accounts.

    Returns:
        Dict with 'connected' status, account list, position count, and positions.
        Position schema matches the IB portfolio output for compatibility.
    """
    try:
        client = get_client()
        fields = [Client.Account.Fields.POSITIONS]

        resp = client.get_accounts(fields=fields)
        resp.raise_for_status()
        all_data = resp.json()

        positions = []
        accounts_seen = []

        for entry in all_data:
            sec = entry.get("securitiesAccount", {})
            acct_num = sec.get("accountNumber", "")
            acct_hash = entry.get("hashValue", "")

            # Filter by account_hash if specified
            if account_hash and acct_hash != account_hash:
                continue

            accounts_seen.append(acct_num)
            for pos in sec.get("positions", []):
                positions.append(_parse_position(pos, acct_num))

            if not all_accounts and not account_hash:
                break  # only first account by default

        return {
            "connected": True,
            "accounts": accounts_seen,
            "position_count": len(positions),
            "positions": positions,
        }

    except FileNotFoundError:
        return {
            "connected": False,
            "error": (
                "Token file not found. Run first_time_setup() to authenticate with Schwab. "
                "See the schwab-account skill for instructions."
            ),
        }
    except EnvironmentError as e:
        return {"connected": False, "error": str(e)}
    except Exception as e:
        return {"connected": False, "error": f"Schwab API error: {e}"}
