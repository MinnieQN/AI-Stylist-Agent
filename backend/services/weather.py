import requests

# Open-Meteo returns the numeric code - convert to words
WMO_SUMMARIES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "depositing rime fog",
    51: "light drizzle", 53: "drizzle", 55: "dense drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain",
    66: "freezing rain", 67: "heavy freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "light rain showers", 81: "rain showers", 82: "violent rain showers",
    85: "snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with heavy hail",
}

"""
Fetch current weather for a city via Open-Meteo (free, no API key).
Synchronous — the agent loop and dispatch are sync like the other nodes.
@param city: city name, e.g. "Chicago"
@return: dict with temperature (F), feels_like, precipitation, summary, wind_speed
@raises: on network failure or unknown city — the agent loop reports the
         error back to the model as the function response
"""
def get_weather(city: str, date: str | None = None) -> dict:
    # geocode the location for latitude and longitude
    geo_url = "https://geocoding-api.open-meteo.com/v1/search"
    geo_response = requests.get(geo_url, params={"name": city, "count": 1}, timeout=10)
    geo_response.raise_for_status()
    geo_data = geo_response.json()
    if not geo_data.get("results"):
        raise ValueError(f"Unknown location: {city}")
    location = geo_data["results"][0]

    # fetch current weather at those coordinates
    weather_url = "https://api.open-meteo.com/v1/forecast"
    weather_params = {
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "current": "temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "timezone": "auto",
    }
    weather_response = requests.get(weather_url, params=weather_params, timeout=10)
    weather_response.raise_for_status()
    current = weather_response.json()["current"]

    return {
        "city": city,
        "temperature_f": current["temperature_2m"],
        "feels_like_f": current["apparent_temperature"],
        "precipitation_mm": current["precipitation"],
        "summary": WMO_SUMMARIES.get(current["weather_code"], "unknown"),
        "wind_speed_mph": current["wind_speed_10m"],
    }
