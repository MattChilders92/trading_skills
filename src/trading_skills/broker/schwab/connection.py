# ABOUTME: Schwab OAuth2 client factory using schwab-py.
# ABOUTME: Loads saved token from file; supports env-var configuration.

import os

import schwab


def _get_credentials() -> tuple[str, str, str]:
    """Read and validate required environment variables.

    Returns:
        Tuple of (api_key, app_secret, token_path).

    Raises:
        EnvironmentError: If any required variable is missing.
    """
    api_key = os.environ.get("SCHWAB_API_KEY")
    app_secret = os.environ.get("SCHWAB_APP_SECRET")
    token_path = os.environ.get("SCHWAB_TOKEN_PATH", os.path.expanduser("~/.schwab_token.json"))

    missing = [
        name for name, val in [("SCHWAB_API_KEY", api_key), ("SCHWAB_APP_SECRET", app_secret)]
        if not val
    ]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "See the schwab-account skill README for setup instructions."
        )
    return api_key, app_secret, token_path  # type: ignore[return-value]


def get_client() -> schwab.client.Client:
    """Return an authenticated Schwab client loaded from the saved token file.

    Reads credentials from environment variables SCHWAB_API_KEY and SCHWAB_APP_SECRET.
    Token file path defaults to ~/.schwab_token.json or SCHWAB_TOKEN_PATH env var.

    Returns:
        Authenticated schwab.client.Client instance.

    Raises:
        EnvironmentError: If SCHWAB_API_KEY or SCHWAB_APP_SECRET are not set.
        FileNotFoundError: If the token file does not exist (run first_time_setup first).
        Exception: If the token is invalid or expired.
    """
    api_key, app_secret, token_path = _get_credentials()
    return schwab.auth.client_from_token_file(token_path, api_key, app_secret)


def first_time_setup(callback_url: str = "https://127.0.0.1:8182") -> None:
    """Run the browser-based OAuth flow to generate and save a token file.

    Only needed once per machine. After this, get_client() can be used directly.

    Args:
        callback_url: HTTPS redirect URL registered in the Schwab developer portal.
                      Defaults to the standard localhost callback.

    Raises:
        EnvironmentError: If SCHWAB_API_KEY or SCHWAB_APP_SECRET are not set.
    """
    api_key, app_secret, token_path = _get_credentials()
    schwab.auth.easy_client(api_key, app_secret, callback_url, token_path)
    print(f"Token saved to {token_path}")
