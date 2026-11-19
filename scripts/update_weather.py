"""Cache Seoul's current model weather and today's forecast for the static site."""
from datetime import datetime
import json
import logging
from pathlib import Path
import sys
import urllib.request
from zoneinfo import ZoneInfo

from update_news import atomic_json

ROOT = Path(__file__).resolve().parents[1]
SEOUL = ZoneInfo("Asia/Seoul")
API_URL = "https://api.open-meteo.com/v1/forecast?latitude=37.5665&longitude=126.9780&current=temperature_2m,weather_code,is_day&daily=temperature_2m_max,temperature_2m_min&timezone=Asia%2FSeoul&forecast_days=1"


def normalize_weather(raw: dict, now: datetime) -> dict:
    current, daily = raw["current"], raw["daily"]
    day = daily["time"][0]
    if day != now.astimezone(SEOUL).date().isoformat() or not current["time"].startswith(day):
        raise ValueError("Weather response is not for today in Seoul")
    low, high = daily["temperature_2m_min"][0], daily["temperature_2m_max"][0]
    if not all(isinstance(v, (int, float)) for v in (low, high, current["temperature_2m"])) or low > high:
        raise ValueError("Invalid weather temperatures")
    return {"location": "서울", "date": day, "timezone": "Asia/Seoul", "source": "Open-Meteo",
            "source_url": "https://open-meteo.com/", "basis": "weather_model_and_daily_forecast",
            "fetched_at": now.isoformat(timespec="seconds"), "weather_time": current["time"] + "+09:00",
            "temperature": current["temperature_2m"], "weather_code": current["weather_code"],
            "is_day": bool(current.get("is_day", 1)), "minimum": low, "maximum": high}


def main():
    try:
        request = urllib.request.Request(API_URL, headers={"User-Agent": "InsuranceMorning/1.0"})
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = json.load(response)
        weather = normalize_weather(raw, datetime.now(SEOUL))
        atomic_json(ROOT / "data/weather.json", weather)
        print(f"Seoul {weather['date']}: {weather['minimum']} / {weather['maximum']} °C")
        return 0
    except Exception as error:
        logging.warning("Weather update unavailable (%s); retaining previous dated cache", type(error).__name__)
        return 0


if __name__ == "__main__":
    sys.exit(main())
