# ABOUTME: Tastytrade session factory using OAuth2 provider credentials.
# ABOUTME: Reads TT_SECRET and TT_REFRESH from environment variables.

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from tastytrade import Session


def _check_env() -> tuple[str, str]:
    """Read and validate required environment variables.

    Returns:
        Tuple of (provider_secret, refresh_token).

    Raises:
        EnvironmentError: If TT_SECRET or TT_REFRESH are not set.
    """
    secret = os.environ.get("TT_SECRET")
    refresh = os.environ.get("TT_REFRESH")
    missing = [name for name, val in [("TT_SECRET", secret), ("TT_REFRESH", refresh)] if not val]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "See the tastytrade-option-chain skill README for setup instructions."
        )
    return secret, refresh  # type: ignore[return-value]


@asynccontextmanager
async def tastytrade_session() -> AsyncGenerator[Session, None]:
    """Async context manager that yields an authenticated Tastytrade session.

    Reads credentials from environment variables TT_SECRET and TT_REFRESH.

    Usage:
        async with tastytrade_session() as session:
            chain = await get_option_chain(session, "SPY")

    Raises:
        EnvironmentError: If credentials are missing.
        Exception: If authentication fails.
    """
    secret, refresh = _check_env()
    async with Session(provider_secret=secret, refresh_token=refresh) as session:
        yield session
