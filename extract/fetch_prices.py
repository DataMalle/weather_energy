"""Hämtar elpriser per elområde från elprisetjustnu.se och laddar upp dem till en Databricks-volym.

Körs av GitHub Actions eftersom Databricks Free Edition blockerar utgående trafik till API:et.
Idempotent: en fil laddas bara upp om den inte redan finns i volymen.
"""
import argparse
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ZONES = ["SE1", "SE2", "SE3", "SE4"]
BASE = "https://www.elprisetjustnu.se/api/v1/prices"
DEFAULT_VOLUME_DIR = "/Volumes/workspace/elvader_pipeline/landing/elpris"


def price_url(day: date, zone: str) -> str:
    return f"{BASE}/{day:%Y}/{day:%m-%d}_{zone}.json"


def days_to_fetch(today: date, days_back: int) -> list[date]:
    """days_back dagar bakåt, idag och imorgon (morgondagens priser publiceras ca 13:00)."""
    return [today - timedelta(days=i) for i in range(days_back, -1, -1)] + [today + timedelta(days=1)]


def target_path(volume_dir: str, zone: str, day: date) -> str:
    return f"{volume_dir}/elpris_{zone}_{day:%Y-%m-%d}.jsonl"


def to_jsonl(zone: str, records: list[dict], fetched_at: str) -> str:
    """En rad per kvartspris, med elområde och hämtningstid inbakade."""
    return "\n".join(json.dumps({"zone": zone, **r, "fetched_at": fetched_at}, ensure_ascii=False) for r in records) + "\n"


def fetch_day(day: date, zone: str, retries: int = 3):
    """Returnerar lista med priser, eller None om dagen inte publicerats (404)."""
    url = price_url(day, zone)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "weather-energy-portfolio/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            err = e
        except Exception as e:  # noqa: BLE001
            err = e
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Misslyckades hämta {url}: {err}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days-back", type=int, default=1)
    ap.add_argument("--volume-dir", default=DEFAULT_VOLUME_DIR)
    ap.add_argument("--dry-run", action="store_true", help="Skriv till ./out istället för Databricks")
    args = ap.parse_args(argv)

    today = datetime.now(ZoneInfo("Europe/Stockholm")).date()
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    client = None
    if not args.dry_run:
        from databricks.sdk import WorkspaceClient  # noqa: PLC0415 - bara när det behövs

        client = WorkspaceClient()  # DATABRICKS_HOST + DATABRICKS_CLIENT_ID/SECRET från miljön

    uploaded = skipped = missing = 0
    for day in days_to_fetch(today, args.days_back):
        for zone in ZONES:
            path = target_path(args.volume_dir, zone, day)
            if client is not None:
                from databricks.sdk.errors import NotFound  # noqa: PLC0415

                try:
                    client.files.get_metadata(path)
                    skipped += 1
                    continue
                except NotFound:
                    pass
            records = fetch_day(day, zone)
            if records is None:
                missing += 1
                print(f"{zone} {day}: inte publicerad ännu")
                continue
            body = to_jsonl(zone, records, fetched_at)
            if args.dry_run:
                os.makedirs("out", exist_ok=True)
                with open(os.path.join("out", os.path.basename(path)), "w", encoding="utf-8") as fh:
                    fh.write(body)
            else:
                client.files.upload(path, io.BytesIO(body.encode("utf-8")), overwrite=False)
            uploaded += 1
            print(f"{zone} {day}: {len(records)} priser -> {path}")
    print(f"Klart: {uploaded} uppladdade, {skipped} fanns redan, {missing} ej publicerade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
