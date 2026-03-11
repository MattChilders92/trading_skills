# ABOUTME: Tests for Tastytrade session factory.
# ABOUTME: Validates env var checks and session creation without live API calls.

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trading_skills.tastytrade.connection import _check_env, tastytrade_session


class TestCheckEnv:
    """Tests for _check_env credential validation."""

    def test_missing_both_vars(self, monkeypatch):
        """Raises EnvironmentError when both TT_SECRET and TT_REFRESH are missing."""
        monkeypatch.delenv("TT_SECRET", raising=False)
        monkeypatch.delenv("TT_REFRESH", raising=False)
        with pytest.raises(EnvironmentError, match="TT_SECRET"):
            _check_env()

    def test_missing_tt_secret(self, monkeypatch):
        """Raises EnvironmentError when TT_SECRET is missing."""
        monkeypatch.delenv("TT_SECRET", raising=False)
        monkeypatch.setenv("TT_REFRESH", "test-refresh")
        with pytest.raises(EnvironmentError, match="TT_SECRET"):
            _check_env()

    def test_missing_tt_refresh(self, monkeypatch):
        """Raises EnvironmentError when TT_REFRESH is missing."""
        monkeypatch.setenv("TT_SECRET", "test-secret")
        monkeypatch.delenv("TT_REFRESH", raising=False)
        with pytest.raises(EnvironmentError, match="TT_REFRESH"):
            _check_env()

    def test_returns_credentials_when_set(self, monkeypatch):
        """Returns (secret, refresh) tuple when both vars are set."""
        monkeypatch.setenv("TT_SECRET", "my-secret")
        monkeypatch.setenv("TT_REFRESH", "my-refresh")
        secret, refresh = _check_env()
        assert secret == "my-secret"
        assert refresh == "my-refresh"


class TestTastytradeSession:
    """Tests for tastytrade_session async context manager."""

    @pytest.mark.asyncio
    async def test_missing_credentials_raises(self, monkeypatch):
        """Session raises EnvironmentError when credentials are missing."""
        monkeypatch.delenv("TT_SECRET", raising=False)
        monkeypatch.delenv("TT_REFRESH", raising=False)
        with pytest.raises(EnvironmentError):
            async with tastytrade_session():
                pass

    @pytest.mark.asyncio
    async def test_session_created_with_credentials(self, monkeypatch):
        """Session is created and yielded when credentials are present."""
        monkeypatch.setenv("TT_SECRET", "my-secret")
        monkeypatch.setenv("TT_REFRESH", "my-refresh")

        mock_session = MagicMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("trading_skills.tastytrade.connection.Session", return_value=mock_ctx):
            async with tastytrade_session() as session:
                assert session is mock_session
