"""WUTT application configuration loaded from environment variables.

Reads all secrets and settings from .env via pydantic-settings.
NEVER hardcode API keys — use this module everywhere.

Pydantic-settings v2 uses ``model_config`` to declare the .env file;
os.getenv calls are avoided so that ALL env parsing flows through one
coherent pipeline.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from .env / environment."""

    model_config = {"env_file": ".env", "extra": "ignore"}

    # ── App ──────────────────────────────────────────────
    app_name: str = "WUTT — AI Personal Stylist"
    debug: bool = False

    # ── Database ─────────────────────────────────────────
    database_url: str = "sqlite:///./wutt.db"

    # ── JWT ──────────────────────────────────────────────
    jwt_secret_key: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24

    # ── Browser sessions ──────────────────────────────────
    session_cookie_name: str = "wutt_session"
    session_expiry_hours: int = 24 * 7

    # ── Temporary Chapter 6 demo login ───────────────────
    demo_login_enabled: bool = False
    demo_login_email: str = ""
    demo_login_password: str = ""

    # ── Google OAuth ──────────────────────────────────────
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    frontend_url: str = "http://localhost:5500"

    # ── Cloudinary ───────────────────────────────────────
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    # ── OpenAI ───────────────────────────────────────────
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4o"

    # ── Gemini ───────────────────────────────────────────
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # ── OpenRouter ───────────────────────────────────────
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_ai_model: str = "openai/gpt-oss-20b:free"

    # ── OpenWeatherMap ───────────────────────────────────
    weather_api_key: str = ""


settings = Settings()


def check_production_safety() -> None:
    """Refuse to start in production with the default JWT secret.

    Called from lifespan startup.  This is a function (not a module-level
    guard) so that imports, tests, and tooling never trip over a missing
    .env file.
    """
    if not settings.debug and settings.jwt_secret_key == "dev-secret-change-in-production":
        raise RuntimeError(
            "JWT_SECRET_KEY is still at its default value. "
            "Set a strong random secret in .env before running in production."
        )
    if settings.demo_login_enabled:
        if not settings.demo_login_email.strip() or not settings.demo_login_password:
            raise RuntimeError(
                "DEMO_LOGIN_ENABLED requires DEMO_LOGIN_EMAIL and "
                "DEMO_LOGIN_PASSWORD."
            )
        if "@" not in settings.demo_login_email or len(settings.demo_login_password) < 8:
            raise RuntimeError(
                "Demo login requires a valid email and a password of at least "
                "8 characters."
            )
