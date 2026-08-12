"""Free, keyless weather lookup via Open-Meteo — used for the daily meal plan."""
import requests

GEOCODE_URL = 'https://geocoding-api.open-meteo.com/v1/search'
FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'

# WMO weather codes -> short human description
WEATHER_CODES = {
    0: 'Clear sky', 1: 'Mostly clear', 2: 'Partly cloudy', 3: 'Overcast',
    45: 'Fog', 48: 'Fog', 51: 'Light drizzle', 53: 'Drizzle', 55: 'Heavy drizzle',
    61: 'Light rain', 63: 'Rain', 65: 'Heavy rain', 71: 'Light snow', 73: 'Snow',
    75: 'Heavy snow', 80: 'Rain showers', 81: 'Rain showers', 82: 'Violent showers',
    95: 'Thunderstorm', 96: 'Thunderstorm with hail', 99: 'Thunderstorm with hail',
}


def get_current_weather(location_text):
    """Look up today's temperature/humidity for a free-text location.
    Returns a dict {temp_f, temp_c, humidity_pct, description, place_name,
    observed_at (location-local "YYYY-MM-DDTHH:MM"), timezone} or None."""
    if not location_text or not location_text.strip():
        return None

    try:
        geo = requests.get(GEOCODE_URL, params={
            'name': location_text.strip(), 'count': 1,
        }, timeout=6).json()
        results = geo.get('results')
        if not results:
            return None

        place = results[0]
        lat, lon = place['latitude'], place['longitude']
        place_name = ', '.join(filter(None, [
            place.get('name'), place.get('admin1'), place.get('country'),
        ]))

        forecast = requests.get(FORECAST_URL, params={
            'latitude': lat, 'longitude': lon,
            'current': 'temperature_2m,relative_humidity_2m,weather_code',
            'temperature_unit': 'fahrenheit',
            'timezone': 'auto',  # so 'current.time' is the location's own local time, not GMT
        }, timeout=6).json()
        current = forecast.get('current')
        if not current:
            return None

        temp_f = current.get('temperature_2m')
        humidity = current.get('relative_humidity_2m')
        code = current.get('weather_code')

        return {
            'temp_f': temp_f,
            'temp_c': round((temp_f - 32) * 5 / 9, 1) if temp_f is not None else None,
            'humidity_pct': humidity,
            'description': WEATHER_CODES.get(code, 'Unknown'),
            'place_name': place_name or location_text,
            'observed_at': current.get('time'),  # e.g. '2026-08-10T14:30' in the pet's local tz
            'timezone': forecast.get('timezone'),  # e.g. 'Asia/Dhaka'
        }
    except Exception:
        return None
