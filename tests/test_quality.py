import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "pipeline"))
from elvader_lib import parse_weather, run_quality_checks, weather_url  # noqa: E402

NOW = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)


def good():
    return {
        "price_rows": 1000, "price_zones": 4, "price_nulls": 0, "price_dupes": 0,
        "price_min": 0.01, "price_max": 3.2,
        "price_min_zone_latest_end": datetime(2026, 10, 13, 22, 0, tzinfo=timezone.utc),
        "weather_rows": 288, "weather_latest_ingest": NOW - timedelta(hours=1),
        "temp_min": -3.0, "temp_max": 14.0, "wind_min": 0.0, "wind_max": 12.0,
    }


def by_name(results):
    return {r["check_name"]: r for r in results}


def test_all_pass_on_good_data():
    assert all(r["passed"] for r in run_quality_checks(good(), now=NOW))


def test_missing_zone_is_critical_failure():
    m = good() | {"price_zones": 3}
    r = by_name(run_quality_checks(m, now=NOW))["prices_all_zones"]
    assert not r["passed"] and r["severity"] == "critical"


def test_duplicates_are_critical():
    r = by_name(run_quality_checks(good() | {"price_dupes": 2}, now=NOW))["prices_unique_key"]
    assert not r["passed"] and r["severity"] == "critical"


def test_stale_prices_only_warn():
    m = good() | {"price_min_zone_latest_end": datetime(2026, 10, 11, 22, 0, tzinfo=timezone.utc)}
    r = by_name(run_quality_checks(m, now=NOW))["prices_cover_today"]
    assert not r["passed"] and r["severity"] == "warn"


def test_old_weather_ingest_warns():
    r = by_name(run_quality_checks(good() | {"weather_latest_ingest": NOW - timedelta(hours=9)}, now=NOW))
    assert not r["weather_recently_ingested"]["passed"]


def test_parse_weather_and_url():
    payload = {"hourly": {"time": ["2026-10-12T00:00", "2026-10-12T01:00"], "temperature_2m": [5.1, 4.9], "wind_speed_10m": [3.0, None]}}
    rows = parse_weather(payload, "SE3", "Stockholm")
    assert rows[0] == ("SE3", "Stockholm", "2026-10-12T00:00", 5.1, 3.0) and rows[1][4] is None
    assert "latitude=59.3" in weather_url(59.3, 18.0)
