import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extract"))
import fetch_prices as fp  # noqa: E402


def test_price_url():
    assert fp.price_url(date(2026, 10, 2), "SE3") == "https://www.elprisetjustnu.se/api/v1/prices/2026/10-02_SE3.json"


def test_days_to_fetch_includes_tomorrow_in_order():
    days = fp.days_to_fetch(date(2026, 10, 12), 2)
    assert days == [date(2026, 10, 10), date(2026, 10, 11), date(2026, 10, 12), date(2026, 10, 13)]


def test_target_path():
    assert fp.target_path("/Volumes/x", "SE1", date(2026, 1, 5)) == "/Volumes/x/elpris_SE1_2026-01-05.jsonl"


def test_to_jsonl_embeds_zone_and_fetched_at():
    recs = [{"SEK_per_kWh": 0.5, "time_start": "a", "time_end": "b"}]
    lines = fp.to_jsonl("SE2", recs, "2026-10-12T10:00:00+00:00").strip().split("\n")
    row = json.loads(lines[0])
    assert row["zone"] == "SE2" and row["SEK_per_kWh"] == 0.5 and row["fetched_at"].startswith("2026-10-12")
