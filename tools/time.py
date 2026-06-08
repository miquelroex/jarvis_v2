# tools/time_tool.py

from langchain.tools import tool
from datetime import datetime
import pytz

@tool
def get_time(city: str = "") -> str:
    """Returns the current time. If a city is specified, returns the time in that city (supported: New York, London, Tokyo, Sydney). Otherwise, returns local time."""
    try:
        city_timezones = {
            "new york": "America/New_York",
            "london": "Europe/London",
            "tokyo": "Asia/Tokyo",
            "sydney": "Australia/Sydney"
        }
        
        if not city or not city.strip():
            current_time = datetime.now().strftime("%H:%M")
            return f"La hora local actual es {current_time}."
            
        city_key = city.lower().strip()
        if city_key not in city_timezones:
            current_time = datetime.now().strftime("%H:%M")
            return f"Lo siento, no conozco la zona horaria para {city}. Como referencia, la hora local es {current_time}."

        timezone = pytz.timezone(city_timezones[city_key])
        current_time = datetime.now(timezone).strftime("%H:%M")
        return f"La hora actual en {city.title()} es {current_time}."
    except Exception as e:
        return f"Error: {e}"
