"""OpenWeatherMap API client -- fetch current conditions by city.

Returns a normalised ``WeatherData`` model so every consumer gets stable,
typed fields.  Weather is always best-effort; callers must handle ``None``.
"""

import httpx
from pydantic import BaseModel

from config import settings

BASE_URL = "https://api.openweathermap.org/data/2.5/weather"
FALLBACK_CITY = "Yangon"


# ── Pydantic model ────────────────────────────────────


class WeatherData(BaseModel):
    """Normalised weather snapshot returned to callers.

    All fields are guaranteed present (no ``None``) when this model exists.
    """

    description: str
    """Human-readable condition, e.g. "clear sky", "light rain"."""

    temperature_c: float
    """Temperature in degrees Celsius."""

    humidity: int
    """Relative humidity as a percentage (0–100)."""

    location: str
    """The city name that resolved successfully."""


# ── Public API ────────────────────────────────────────


def get_current_weather(city: str) -> WeatherData | None:
    """Fetch current weather for *city*, falling back to Yangon.

    Args:
        city: A city name recognised by OpenWeatherMap (e.g. "Yangon").

    Returns:
        ``WeatherData`` with normalised fields, or ``None`` when the
        API key is missing or both the primary city *and* the fallback
        fail.

    Behaviour:
        1. Try *city*.
        2. If *city* is not Yangon and step 1 failed, try Yangon.
        3. Return ``None`` only when all attempts are exhausted.

        Weather is non-critical -- callers treat ``None`` as "no weather
        context available" and continue gracefully.
    """
    if not settings.weather_api_key:
        return None

    # Try the primary city first
    result = _fetch(city)
    if result is not None:
        return result

    # Fallback to Yangon (only if the primary wasn't already Yangon)
    if city.lower() != FALLBACK_CITY.lower():
        result = _fetch(FALLBACK_CITY)
        if result is not None:
            return result

    return None


# ── Internal helpers ──────────────────────────────────


def _fetch(city: str) -> WeatherData | None:
    """Call the OpenWeatherMap API for *city* and normalise the response.

    Returns ``None`` on any failure (network, bad status, missing fields).
    """
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                BASE_URL,
                params={
                    "q": city,
                    "appid": settings.weather_api_key,
                    "units": "metric",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            # Extract and validate required fields
            weather_list = data.get("weather")
            main_block = data.get("main")

            if not weather_list or not main_block:
                return None

            description = weather_list[0].get("description")
            temperature = main_block.get("temp")
            humidity = main_block.get("humidity")

            if not description or temperature is None or humidity is None:
                return None

            return WeatherData(
                description=str(description),
                temperature_c=float(temperature),
                humidity=int(humidity),
                location=city,
            )

    except Exception:
        return None
