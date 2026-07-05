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
