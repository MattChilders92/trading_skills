# ABOUTME: Tests for Tastytrade option chain fetcher.
# ABOUTME: Validates output shape, expiry filtering, error handling — no live API calls.

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trading_skills.tastytrade.options import (
    _build_option_record,
    _decimal_to_float,
    _parse_expiry,
    get_option_chain_tastytrade,
)


class TestParseExpiry:
    """Tests for _parse_expiry date parsing."""

    def test_valid_date(self):
        """Parses valid YYYY-MM-DD string."""
        assert _parse_expiry("2026-03-20") == date(2026, 3, 20)

    def test_invalid_format_raises(self):
        """Raises ValueError for non-YYYY-MM-DD input."""
        with pytest.raises(ValueError, match="Invalid expiry format"):
            _parse_expiry("03/20/2026")

    def test_invalid_date_raises(self):
        """Raises ValueError for impossible date."""
        with pytest.raises(ValueError):
            _parse_expiry("2026-13-01")


class TestDecimalToFloat:
    """Tests for _decimal_to_float helper."""

    def test_none_returns_none(self):
        assert _decimal_to_float(None) is None

    def test_decimal_converted_and_rounded(self):
        assert _decimal_to_float(Decimal("2.279999")) == 2.28

    def test_zero_decimal(self):
        assert _decimal_to_float(Decimal("0")) == 0.0


class TestBuildOptionRecord:
    """Tests for _build_option_record single-option builder."""

    def _make_option(self, strike, symbol, option_type):
        opt = MagicMock()
        opt.strike_price = Decimal(str(strike))
        opt.symbol = symbol
        return opt

    def _make_market_data(self, bid, ask, mark, volume, oi):
        md = MagicMock()
        md.bid = Decimal(str(bid)) if bid is not None else None
        md.ask = Decimal(str(ask)) if ask is not None else None
        md.mark = Decimal(str(mark)) if mark is not None else None
        md.volume = Decimal(str(volume)) if volume is not None else None
        md.open_interest = Decimal(str(oi)) if oi is not None else None
        return md

    def test_record_with_market_data(self):
        """Builds correct record when market data is available."""
        opt = self._make_option(225, "BA  260320C00225000", None)
        md = self._make_market_data(bid=1.76, ask=2.35, mark=2.05, volume=903, oi=3089)
        record = _build_option_record(opt, {"BA  260320C00225000": md})
        assert record["strike"] == 225.0
        assert record["bid"] == 1.76
        assert record["ask"] == 2.35
        assert record["lastPrice"] == 2.05
        assert record["volume"] == 903
        assert record["openInterest"] == 3089
        assert record["impliedVolatility"] is None  # not provided via REST

    def test_record_missing_market_data(self):
        """Returns None fields when market data is absent for a symbol."""
        opt = self._make_option(230, "BA  260320C00230000", None)
        record = _build_option_record(opt, {})
        assert record["strike"] == 230.0
        assert record["bid"] is None
        assert record["ask"] is None
        assert record["volume"] is None


class TestGetOptionChainTastytrade:
    """Tests for get_option_chain_tastytrade async function."""

    def _make_option(self, strike, symbol, option_type_value):
        from tastytrade.instruments import OptionType

        opt = MagicMock()
        opt.strike_price = Decimal(str(strike))
        opt.symbol = symbol
        opt.option_type = (
            OptionType.CALL if option_type_value == "C" else OptionType.PUT
        )
        return opt

    def _make_market_data(self, symbol, bid=1.5, ask=2.0, mark=1.75):
        md = MagicMock()
        md.symbol = symbol
        md.bid = Decimal(str(bid))
        md.ask = Decimal(str(ask))
        md.mark = Decimal(str(mark))
        md.volume = Decimal("100")
        md.open_interest = Decimal("500")
        return md

    @pytest.mark.asyncio
    async def test_expiry_not_in_chain_returns_error(self, monkeypatch):
        """Returns error dict when requested expiry has no options."""
        monkeypatch.setenv("TT_SECRET", "s")
        monkeypatch.setenv("TT_REFRESH", "r")

        mock_session = MagicMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("trading_skills.tastytrade.options.tastytrade_session", return_value=mock_ctx):
            with patch(
                "trading_skills.tastytrade.options.get_option_chain",
                new=AsyncMock(return_value={date(2026, 4, 17): []}),
            ):
                result = await get_option_chain_tastytrade("BA", "2026-03-20")
        assert "error" in result
        assert "2026-03-20" in result["error"]

    @pytest.mark.asyncio
    async def test_missing_credentials_returns_error(self, monkeypatch):
        """Returns error dict when env vars are missing."""
        monkeypatch.delenv("TT_SECRET", raising=False)
        monkeypatch.delenv("TT_REFRESH", raising=False)
        result = await get_option_chain_tastytrade("BA", "2026-03-20")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_successful_chain_output_shape(self, monkeypatch):
        """Returns correct output shape matching yfinance schema."""
        monkeypatch.setenv("TT_SECRET", "s")
        monkeypatch.setenv("TT_REFRESH", "r")

        target_date = date(2026, 3, 20)
        call_sym = "BA  260320C00225000"
        put_sym = "BA  260320P00225000"
        options = [
            self._make_option(225, call_sym, "C"),
            self._make_option(225, put_sym, "P"),
        ]
        market_data = [
            self._make_market_data(call_sym, bid=1.76, ask=2.35, mark=2.05),
            self._make_market_data(put_sym, bid=9.85, ask=11.15, mark=10.50),
        ]
        equity_md = MagicMock()
        equity_md.mark = Decimal("214.74")

        mock_session = MagicMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("trading_skills.tastytrade.options.tastytrade_session", return_value=mock_ctx):
            with patch(
                "trading_skills.tastytrade.options.get_option_chain",
                new=AsyncMock(return_value={target_date: options}),
            ):
                with patch(
                    "trading_skills.tastytrade.options.get_market_data_by_type",
                    new=AsyncMock(side_effect=[market_data, [equity_md]]),
                ):
                    result = await get_option_chain_tastytrade("BA", "2026-03-20")

        assert result["symbol"] == "BA"
        assert result["source"] == "tastytrade"
        assert "fetched_at" in result
        assert result["expiry"] == "2026-03-20"
        assert result["underlying_price"] == 214.74
        assert len(result["calls"]) == 1
        assert len(result["puts"]) == 1
        assert result["calls"][0]["strike"] == 225.0
        assert result["calls"][0]["bid"] == 1.76

    @pytest.mark.asyncio
    async def test_output_shape_matches_yfinance_keys(self, monkeypatch):
        """Output dict has identical top-level keys to yfinance option chain."""
        monkeypatch.setenv("TT_SECRET", "s")
        monkeypatch.setenv("TT_REFRESH", "r")

        target_date = date(2026, 3, 20)
        options = [self._make_option(225, "BA  260320C00225000", "C")]
        market_data = [self._make_market_data("BA  260320C00225000")]
        equity_md = MagicMock()
        equity_md.mark = Decimal("214.74")

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("trading_skills.tastytrade.options.tastytrade_session", return_value=mock_ctx):
            with patch(
                "trading_skills.tastytrade.options.get_option_chain",
                new=AsyncMock(return_value={target_date: options}),
            ):
                with patch(
                    "trading_skills.tastytrade.options.get_market_data_by_type",
                    new=AsyncMock(side_effect=[market_data, [equity_md]]),
                ):
                    result = await get_option_chain_tastytrade("BA", "2026-03-20")

        expected_keys = {"symbol", "source", "fetched_at", "expiry", "underlying_price",
                         "calls", "puts"}
        assert expected_keys.issubset(result.keys())

        expected_record_keys = {"strike", "bid", "ask", "lastPrice", "volume",
                                "openInterest", "impliedVolatility", "inTheMoney"}
        for record in result["calls"] + result["puts"]:
            assert expected_record_keys == set(record.keys())
