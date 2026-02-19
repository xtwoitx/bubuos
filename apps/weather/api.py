"""Weather data fetching — Open-Meteo + ip-api.com geolocation."""

import datetime
import json
import urllib.request
import urllib.parse

# WMO weather code → (icon_key, condition_text)
WMO_CODES = {
    0: ("sun", "Clear sky"),
    1: ("partly_cloudy", "Mainly clear"),
    2: ("partly_cloudy", "Partly cloudy"),
    3: ("cloudy", "Overcast"),
    45: ("fog", "Fog"),
    48: ("fog", "Rime fog"),
    51: ("rain", "Light drizzle"),
    53: ("rain", "Drizzle"),
    55: ("rain", "Dense drizzle"),
    56: ("rain", "Freezing drizzle"),
    57: ("rain", "Heavy freezing drizzle"),
    61: ("rain", "Slight rain"),
    63: ("heavy_rain", "Moderate rain"),
    65: ("heavy_rain", "Heavy rain"),
    66: ("rain", "Freezing rain"),
    67: ("heavy_rain", "Heavy freezing rain"),
    71: ("snow", "Slight snow"),
    73: ("snow", "Moderate snow"),
    75: ("snow", "Heavy snow"),
    77: ("snow", "Snow grains"),
    80: ("rain", "Slight showers"),
    81: ("rain", "Moderate showers"),
    82: ("heavy_rain", "Violent showers"),
    85: ("snow", "Light snow showers"),
    86: ("snow", "Heavy snow showers"),
    95: ("thunder", "Thunderstorm"),
    96: ("thunder", "Thunderstorm, slight hail"),
    99: ("thunder", "Thunderstorm, heavy hail"),
}

_HEADERS = {"User-Agent": "BubuOS/1.0"}


def _get(url, timeout=10):
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def fetch_location():
    """Get lat/lon/city from IP geolocation. Returns dict or None."""
    try:
        data = _get("http://ip-api.com/json/?fields=lat,lon,city")
        return {"lat": data["lat"], "lon": data["lon"], "city": data.get("city", "Unknown")}
    except Exception:
        return None


def geocode_city(city_name):
    """Geocode city name via Open-Meteo. Returns (lat, lon, name) or None."""
    try:
        q = urllib.parse.quote(city_name)
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={q}&count=1&language=en"
        data = _get(url)
        results = data.get("results", [])
        if results:
            r = results[0]
            return (r["latitude"], r["longitude"], r["name"])
    except Exception:
        pass
    return None


def fetch_weather(lat, lon):
    """Fetch current weather + 5-day forecast. Returns dict or None."""
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
            f"&daily=weather_code,temperature_2m_max,temperature_2m_min"
            f"&timezone=auto&forecast_days=5"
        )
        data = _get(url)

        cur = data.get("current", {})
        wmo = cur.get("weather_code", 0)
        icon_key, condition = WMO_CODES.get(wmo, ("sun", "Unknown"))

        current = {
            "temp": cur.get("temperature_2m"),
            "humidity": cur.get("relative_humidity_2m"),
            "wind_speed": cur.get("wind_speed_10m"),
            "weather_code": wmo,
            "condition": condition,
            "icon_key": icon_key,
        }

        daily = data.get("daily", {})
        dates = daily.get("time", [])
        codes = daily.get("weather_code", [])
        highs = daily.get("temperature_2m_max", [])
        lows = daily.get("temperature_2m_min", [])

        forecast = []
        for i in range(min(5, len(dates))):
            dt = datetime.date.fromisoformat(dates[i])
            fcode = codes[i] if i < len(codes) else 0
            f_icon, _ = WMO_CODES.get(fcode, ("sun", "Unknown"))
            forecast.append({
                "day_name": dt.strftime("%a"),
                "icon_key": f_icon,
                "high": highs[i] if i < len(highs) else 0,
                "low": lows[i] if i < len(lows) else 0,
            })

        return {"current": current, "forecast": forecast}
    except Exception:
        return None
