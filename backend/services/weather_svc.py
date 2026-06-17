"""OpenWeatherMap API client — fetch current conditions by city."""

import httpx
from config import settings

BASE_URL = "https://api.openweathermap.org/data/2.5/weather"


def get_current_weather(city: str) -> dict[str, str | float] | None:
    """Fetch current weather for *city*.

    Returns:
        ``{"description": "...", "temperature_c": 30.0}`` or ``None`` on failure.

        Temperature is converted from Kelvin to Celsius.
    """
    if not settings.weather_api_key:
        return None

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
            return {
                "description": data["weather"][0]["description"],
                "temperature_c": data["main"]["temp"],
            }
    except Exception:
        return None  # Weather is best-effort — don't break the request
