"""Verify local Google OAuth configuration without printing credentials."""

from pathlib import Path
import sys
from urllib.parse import parse_qs, urlsplit

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from config import settings  # noqa: E402
from routes.auth import OAUTH_STATE_COOKIE, google_start  # noqa: E402


LOCAL_FRONTEND_URL = "http://localhost:5500"
LOCAL_REDIRECT_URI = "http://localhost:8000/auth/google/callback"


def _configured(value: str) -> bool:
    """Return whether a setting contains a non-placeholder value."""
    normalized = value.strip().lower()
    return bool(normalized) and not normalized.startswith("your-")


def main() -> int:
    """Print safe local checks and return nonzero when setup is incomplete."""
    checks = {
        "GOOGLE_CLIENT_ID is configured": _configured(settings.google_client_id),
        "GOOGLE_CLIENT_SECRET is configured": _configured(
            settings.google_client_secret
        ),
        "GOOGLE_REDIRECT_URI matches local callback": (
            settings.google_redirect_uri == LOCAL_REDIRECT_URI
        ),
        "FRONTEND_URL matches local frontend": (
            settings.frontend_url == LOCAL_FRONTEND_URL
        ),
        "DEBUG enables local cookie behavior": settings.debug is True,
    }

    for label, passed in checks.items():
        print(f"[{'OK' if passed else 'MISSING'}] {label}")

    if not all(checks.values()):
        print(
            "\nGoogle OAuth is not ready. Update backend/.env using "
            "../.env.example and restart the backend."
        )
        return 1

    response = google_start()
    location = response.headers["location"]
    query = parse_qs(urlsplit(location).query)
    set_cookie = response.headers.getlist("set-cookie")
    start_checks = {
        "Google authorization redirect is generated": (
            response.status_code == 302
            and urlsplit(location).netloc == "accounts.google.com"
        ),
        "Configured callback is sent to Google": (
            query.get("redirect_uri") == [LOCAL_REDIRECT_URI]
        ),
        "State, nonce, and PKCE are present": all(
            query.get(name)
            for name in ("state", "nonce", "code_challenge")
        ),
        "HTTP-only OAuth transaction cookie is set": any(
            header.startswith(f"{OAUTH_STATE_COOKIE}=")
            and "HttpOnly" in header
            for header in set_cookie
        ),
    }

    for label, passed in start_checks.items():
        print(f"[{'OK' if passed else 'FAILED'}] {label}")

    if not all(start_checks.values()):
        print("\nGoogle OAuth configuration loaded, but the start flow is invalid.")
        return 1

    print(
        "\nGoogle OAuth local configuration is ready. Start the backend and "
        "frontend, then test Continue with Google in the browser."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
