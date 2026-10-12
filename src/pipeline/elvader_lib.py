"""Gemensam logik för pipeline-notebooks. Ren Python så att den kan enhetstestas utan Spark."""
import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

STOCKHOLM = ZoneInfo("Europe/Stockholm")

# Elområde -> (referensstad för väder, latitud, longitud)
ZONES = {
    "SE1": ("Luleå", 65.5848, 22.1547),
    "SE2": ("Östersund", 63.1792, 14.6357),
    "SE3": ("Stockholm", 59.3293, 18.0686),
    "SE4": ("Malmö", 55.6050, 13.0038),
}


def weather_url(lat: float, lon: float, past_days: int = 1, forecast_days: int = 2) -> str:
    return (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=temperature_2m,wind_speed_10m&wind_speed_unit=ms"
        f"&timezone=Europe%2FStockholm&past_days={past_days}&forecast_days={forecast_days}"
    )


def fetch_json(url: str, retries: int = 3, timeout: int = 30):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "weather-energy-portfolio/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except Exception as e:  # noqa: BLE001 - retry på alla nätverksfel
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Kunde inte hämta {url}: {last}")


def parse_weather(payload: dict, zone: str, city: str) -> list[tuple]:
    """(zone, city, ts_local, temperature_c, wind_ms) per timme."""
    h = payload["hourly"]
    return [
        (zone, city, t, temp, wind)
        for t, temp, wind in zip(h["time"], h["temperature_2m"], h["wind_speed_10m"])
    ]


def run_quality_checks(m: dict, now: datetime | None = None) -> list[dict]:
    """Utvärderar datakvalitet utifrån mätvärden som notebooken räknat fram.

    severity 'critical' stoppar publiceringen av gold-tabellerna, 'warn' visas bara i appen.
    """
    now = now or datetime.now(timezone.utc)
    tomorrow_start = (
        datetime.combine(now.astimezone(STOCKHOLM).date() + timedelta(days=1), datetime.min.time(), tzinfo=STOCKHOLM)
    ).astimezone(timezone.utc)

    def check(name, severity, passed, detail):
        return {"check_name": name, "severity": severity, "passed": bool(passed), "detail": detail}

    results = [
        check("prices_not_empty", "critical", m["price_rows"] > 0, f"{m['price_rows']} rader"),
        check("prices_all_zones", "critical", m["price_zones"] == len(ZONES), f"{m['price_zones']} av {len(ZONES)} elområden"),
        check("prices_no_nulls", "critical", m["price_nulls"] == 0, f"{m['price_nulls']} saknade priser"),
        check("prices_unique_key", "critical", m["price_dupes"] == 0, f"{m['price_dupes']} dubbletter på (zone, tid)"),
        check(
            "prices_plausible_range",
            "warn",
            m["price_min"] is not None and -5 <= m["price_min"] and m["price_max"] <= 50,
            f"min {m['price_min']} / max {m['price_max']} SEK per kWh",
        ),
        check(
            "prices_cover_today",
            "warn",
            m["price_min_zone_latest_end"] is not None and m["price_min_zone_latest_end"] >= tomorrow_start,
            f"senaste prisslut per område (minsta): {m['price_min_zone_latest_end']}",
        ),
        check("weather_not_empty", "critical", m["weather_rows"] > 0, f"{m['weather_rows']} rader"),
        check(
            "weather_plausible_range",
            "warn",
            m["temp_min"] is not None and -50 <= m["temp_min"] and m["temp_max"] <= 45 and 0 <= m["wind_min"] and m["wind_max"] <= 60,
            f"temp {m['temp_min']}..{m['temp_max']} C, vind {m['wind_min']}..{m['wind_max']} m/s",
        ),
        check(
            "weather_covers_price_history",
            "warn",
            m["weather_coverage"] >= 0.95,
            f"{m['weather_coverage']:.0%} av pristimmarna har väderdata (krav 95%)",
        ),
        check(
            "weather_recently_ingested",
            "warn",
            m["weather_latest_ingest"] is not None and now - m["weather_latest_ingest"] <= timedelta(hours=6),
            f"senast hämtad {m['weather_latest_ingest']}",
        ),
    ]
    return results
