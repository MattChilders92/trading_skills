# ABOUTME: Tests for Schwab portfolio position fetching module.
# ABOUTME: Validates position parsing, option fields, and account filtering — no live API calls.

from unittest.mock import MagicMock, patch

from trading_skills.broker.schwab.portfolio import _parse_position, get_portfolio


def _make_equity_pos(symbol: str, quantity: float, avg_cost: float, market_value: float):
    """Build a minimal equity position dict for testing."""
    return {
        "longQuantity": quantity,
        "shortQuantity": 0,
        "averagePrice": avg_cost,
        "marketValue": market_value,
        "longOpenProfitLoss": market_value - (avg_cost * quantity),
        "instrument": {
            "assetType": "EQUITY",
            "symbol": symbol,
        },
    }


def _make_option_pos(
    symbol: str, strike: float, expiry: str, put_call: str, quantity: float, avg_cost: float
):
    """Build a minimal option position dict for testing."""
    return {
        "longQuantity": quantity,
        "shortQuantity": 0,
        "averagePrice": avg_cost,
        "marketValue": avg_cost * quantity * 100,
        "longOpenProfitLoss": 0.0,
        "instrument": {
            "assetType": "OPTION",
            "symbol": (
                f"{symbol}  {expiry[2:]}"
                f"{'C' if put_call == 'CALL' else 'P'}{int(strike * 1000):08d}"
            ),
            "underlyingSymbol": symbol,
            "putCall": put_call,
            "strikePrice": strike,
            "expirationDate": f"20{expiry[:2]}-{expiry[2:4]}-{expiry[4:]}T00:00:00+0000",
        },
    }


class TestParsePosition:
    """Tests for _parse_position helper."""

    def test_equity_position(self):
        """Parses equity position with correct sec_type and null option fields."""
        pos = _make_equity_pos("BA", 100, 210.0, 21500.0)
        result = _parse_position(pos, "111")
        assert result["sec_type"] == "STK"
        assert result["symbol"] == "BA"
        assert result["quantity"] == 100
        assert result["avg_cost"] == 210.0
        assert result["market_value"] == 21500.0
        assert result["strike"] is None
        assert result["expiry"] is None
        assert result["right"] is None

    def test_option_position_call(self):
        """Parses call option with correct strike, expiry, and right fields."""
        pos = _make_option_pos("BA", 225.0, "260320", "CALL", 1, 2.28)
        result = _parse_position(pos, "111")
        assert result["sec_type"] == "OPT"
        assert result["symbol"] == "BA"
        assert result["strike"] == 225.0
        assert result["right"] == "C"
        assert result["expiry"] == "20260320"

    def test_option_position_put(self):
        """Parses put option with right=P."""
        pos = _make_option_pos("BA", 210.0, "260320", "PUT", 1, 5.0)
        result = _parse_position(pos, "111")
        assert result["right"] == "P"

    def test_short_position_has_negative_quantity(self):
        """Short positions have negative quantity."""
        pos = {
            "longQuantity": 0,
            "shortQuantity": 2,
            "averagePrice": 2.28,
            "marketValue": -456.0,
            "shortOpenProfitLoss": 50.0,
            "instrument": {"assetType": "OPTION", "symbol": "BA  260320C00225000",
                           "underlyingSymbol": "BA", "putCall": "CALL",
                           "strikePrice": 225.0, "expirationDate": "2026-03-20T00:00:00+0000"},
        }
        result = _parse_position(pos, "111")
        assert result["quantity"] == -2


class TestGetPortfolio:
    """Tests for get_portfolio with mocked Schwab client."""

    def test_missing_env_vars_returns_not_connected(self, monkeypatch):
        """Returns connected=False when env vars are missing."""
        monkeypatch.delenv("SCHWAB_API_KEY", raising=False)
        monkeypatch.delenv("SCHWAB_APP_SECRET", raising=False)
        result = get_portfolio()
        assert result["connected"] is False

    def test_token_file_not_found_returns_not_connected(self, monkeypatch):
        """Returns connected=False when token file is missing."""
        monkeypatch.setenv("SCHWAB_API_KEY", "k")
        monkeypatch.setenv("SCHWAB_APP_SECRET", "s")
        with patch(
            "trading_skills.broker.schwab.portfolio.get_client",
            side_effect=FileNotFoundError("no token"),
        ):
            result = get_portfolio()
        assert result["connected"] is False

    def test_default_returns_first_account_positions(self, monkeypatch):
        """Default call returns positions for the first account only."""
        monkeypatch.setenv("SCHWAB_API_KEY", "k")
        monkeypatch.setenv("SCHWAB_APP_SECRET", "s")

        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {
                "hashValue": "hash_111",
                "securitiesAccount": {
                    "accountNumber": "111",
                    "positions": [_make_equity_pos("BA", 100, 210.0, 21500.0)],
                },
            },
            {
                "hashValue": "hash_222",
                "securitiesAccount": {
                    "accountNumber": "222",
                    "positions": [_make_equity_pos("AAPL", 50, 180.0, 9200.0)],
                },
            },
        ]
        mock_client = MagicMock()
        mock_client.get_accounts.return_value = mock_resp

        with patch("trading_skills.broker.schwab.portfolio.get_client", return_value=mock_client):
            result = get_portfolio()

        assert result["connected"] is True
        assert result["position_count"] == 1
        assert result["positions"][0]["symbol"] == "BA"

    def test_all_accounts_returns_all_positions(self, monkeypatch):
        """all_accounts=True returns positions from all linked accounts."""
        monkeypatch.setenv("SCHWAB_API_KEY", "k")
        monkeypatch.setenv("SCHWAB_APP_SECRET", "s")

        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {
                "hashValue": "h1",
                "securitiesAccount": {
                    "accountNumber": "111",
                    "positions": [_make_equity_pos("BA", 100, 210.0, 21500.0)],
                },
            },
            {
                "hashValue": "h2",
                "securitiesAccount": {
                    "accountNumber": "222",
                    "positions": [_make_equity_pos("AAPL", 50, 180.0, 9200.0)],
                },
            },
        ]
        mock_client = MagicMock()
        mock_client.get_accounts.return_value = mock_resp

        with patch("trading_skills.broker.schwab.portfolio.get_client", return_value=mock_client):
            result = get_portfolio(all_accounts=True)

        assert result["connected"] is True
        assert result["position_count"] == 2
        symbols = {p["symbol"] for p in result["positions"]}
        assert symbols == {"BA", "AAPL"}

    def test_position_schema_has_required_keys(self, monkeypatch):
        """Each position dict contains all required schema keys."""
        monkeypatch.setenv("SCHWAB_API_KEY", "k")
        monkeypatch.setenv("SCHWAB_APP_SECRET", "s")

        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {
                "hashValue": "h1",
                "securitiesAccount": {
                    "accountNumber": "111",
                    "positions": [_make_equity_pos("BA", 100, 210.0, 21500.0)],
                },
            }
        ]
        mock_client = MagicMock()
        mock_client.get_accounts.return_value = mock_resp

        with patch("trading_skills.broker.schwab.portfolio.get_client", return_value=mock_client):
            result = get_portfolio()

        required_keys = {
            "account", "symbol", "sec_type", "currency", "quantity",
            "avg_cost", "market_price", "market_value", "unrealized_pnl",
            "strike", "expiry", "right", "underlying_price",
        }
        for pos in result["positions"]:
            assert required_keys.issubset(pos.keys())
