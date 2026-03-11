# ABOUTME: Fetches account summary from Charles Schwab (read-only).
# ABOUTME: Returns net liquidation, cash, buying power per account.

from schwab.client import Client

from trading_skills.broker.schwab.connection import get_client


def _parse_balances(securities_account: dict) -> dict:
    """Parse balance fields from a securitiesAccount response.

    Args:
        securities_account: The 'securitiesAccount' dict from the Schwab API response.

    Returns:
        Dict with normalized balance fields.
    """
    balances = securities_account.get("currentBalances", {})
    return {
        "net_liquidation": balances.get("liquidationValue"),
        "total_cash": balances.get("cashBalance"),
        "buying_power": balances.get("buyingPower"),
        "available_funds": balances.get("availableFunds"),
        "maintenance_margin": balances.get("maintenanceRequirement"),
        "unrealized_pnl": securities_account.get("aggregatedBalance", {}).get(
            "currentLiquidationValue"
        ),
    }


def _parse_account(entry: dict) -> dict:
    """Parse a single account entry from the Schwab API response.

    Args:
        entry: Account dict from the accounts response list.

    Returns:
        Dict with account ID, balances, and currency.
    """
    sec = entry.get("securitiesAccount", {})
    return {
        "account": sec.get("accountNumber", ""),
        "summary": _parse_balances(sec),
        "currency": "USD",
    }


def get_account_summary(account_hash: str | None = None, all_accounts: bool = False) -> dict:
    """Fetch account summary from Charles Schwab.

    Args:
        account_hash: Specific account hash to fetch. If not provided, uses first account.
        all_accounts: If True, fetch summaries for all linked accounts.

    Returns:
        Dict with 'connected' status and list of account summaries, each containing
        account number, net liquidation, cash balance, and buying power.
    """
    try:
        client = get_client()
        fields = [Client.Account.Fields.POSITIONS]

        if all_accounts or account_hash is None:
            resp = client.get_accounts(fields=fields)
            resp.raise_for_status()
            data = resp.json()
            accounts = [_parse_account(entry) for entry in data]

            if not all_accounts and accounts:
                accounts = accounts[:1]
        else:
            resp = client.get_account(account_hash, fields=fields)
            resp.raise_for_status()
            data = resp.json()
            accounts = [_parse_account(data)]

        return {
            "connected": True,
            "accounts": accounts,
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
