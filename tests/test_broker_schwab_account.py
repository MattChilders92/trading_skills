# ABOUTME: Tests for Schwab account summary module.
# ABOUTME: Validates balance parsing, error handling, and account filtering — no live API calls.

from unittest.mock import MagicMock, patch

from trading_skills.broker.schwab.account import _parse_balances, get_account_summary


def _make_account_entry(account_number: str, balances: dict, positions: list | None = None):
    """Build a minimal Schwab accounts response entry for testing."""
    return {
        "hashValue": f"hash_{account_number}",
        "securitiesAccount": {
            "accountNumber": account_number,
            "currentBalances": balances,
            "positions": positions or [],
        },
    }


class TestParseBalances:
    """Tests for _parse_balances helper."""

    def test_all_fields_present(self):
        """Parses all expected balance fields."""
        sec = {
            "currentBalances": {
                "liquidationValue": 50000.0,
                "cashBalance": 10000.0,
                "buyingPower": 20000.0,
                "availableFunds": 18000.0,
                "maintenanceRequirement": 5000.0,
            }
        }
        result = _parse_balances(sec)
        assert result["net_liquidation"] == 50000.0
        assert result["total_cash"] == 10000.0
        assert result["buying_power"] == 20000.0
        assert result["available_funds"] == 18000.0
        assert result["maintenance_margin"] == 5000.0

    def test_missing_fields_return_none(self):
        """Returns None for missing balance fields."""
        result = _parse_balances({})
        assert result["net_liquidation"] is None
        assert result["total_cash"] is None
        assert result["buying_power"] is None


class TestGetAccountSummary:
    """Tests for get_account_summary with mocked Schwab client."""

    def test_missing_env_vars_returns_not_connected(self, monkeypatch):
        """Returns connected=False when env vars are missing."""
        monkeypatch.delenv("SCHWAB_API_KEY", raising=False)
        monkeypatch.delenv("SCHWAB_APP_SECRET", raising=False)
        result = get_account_summary()
        assert result["connected"] is False
        assert "error" in result

    def test_token_file_not_found_returns_not_connected(self, monkeypatch):
        """Returns connected=False when token file is missing."""
        monkeypatch.setenv("SCHWAB_API_KEY", "test-key")
        monkeypatch.setenv("SCHWAB_APP_SECRET", "test-secret")
        with patch(
            "trading_skills.broker.schwab.account.get_client",
            side_effect=FileNotFoundError("no token"),
        ):
            result = get_account_summary()
        assert result["connected"] is False
        assert "Token file not found" in result["error"]

    def test_default_returns_first_account(self, monkeypatch):
        """Default call (no args) returns only the first account."""
        monkeypatch.setenv("SCHWAB_API_KEY", "k")
        monkeypatch.setenv("SCHWAB_APP_SECRET", "s")

        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            _make_account_entry("111", {"liquidationValue": 50000.0}),
            _make_account_entry("222", {"liquidationValue": 75000.0}),
        ]
        mock_client = MagicMock()
        mock_client.get_accounts.return_value = mock_resp

        with patch("trading_skills.broker.schwab.account.get_client", return_value=mock_client):
            result = get_account_summary()

        assert result["connected"] is True
        assert len(result["accounts"]) == 1
        assert result["accounts"][0]["account"] == "111"

    def test_all_accounts_returns_all(self, monkeypatch):
        """all_accounts=True returns all linked accounts."""
        monkeypatch.setenv("SCHWAB_API_KEY", "k")
        monkeypatch.setenv("SCHWAB_APP_SECRET", "s")

        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            _make_account_entry("111", {"liquidationValue": 50000.0}),
            _make_account_entry("222", {"liquidationValue": 75000.0}),
        ]
        mock_client = MagicMock()
        mock_client.get_accounts.return_value = mock_resp

        with patch("trading_skills.broker.schwab.account.get_client", return_value=mock_client):
            result = get_account_summary(all_accounts=True)

        assert result["connected"] is True
        assert len(result["accounts"]) == 2
        assert result["accounts"][1]["account"] == "222"

    def test_specific_account_hash(self, monkeypatch):
        """Fetches single account when hash is provided."""
        monkeypatch.setenv("SCHWAB_API_KEY", "k")
        monkeypatch.setenv("SCHWAB_APP_SECRET", "s")

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "hashValue": "hash_111",
            "securitiesAccount": {
                "accountNumber": "111",
                "currentBalances": {"liquidationValue": 50000.0},
                "positions": [],
            },
        }
        mock_client = MagicMock()
        mock_client.get_account.return_value = mock_resp

        with patch("trading_skills.broker.schwab.account.get_client", return_value=mock_client):
            result = get_account_summary(account_hash="hash_111")

        assert result["connected"] is True
        assert result["accounts"][0]["account"] == "111"
        assert result["accounts"][0]["summary"]["net_liquidation"] == 50000.0

    def test_api_error_returns_not_connected(self, monkeypatch):
        """Returns connected=False on unexpected API error."""
        monkeypatch.setenv("SCHWAB_API_KEY", "k")
        monkeypatch.setenv("SCHWAB_APP_SECRET", "s")

        with patch(
            "trading_skills.broker.schwab.account.get_client",
            side_effect=Exception("network error"),
        ):
            result = get_account_summary()

        assert result["connected"] is False
        assert "Schwab API error" in result["error"]
