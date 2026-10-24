"""
This script uses the OpenAQ API to retrieve the inventory of PM2.5 stations in Hanoi and saves it as a CSV file.
The CSV file is in data/interim/stations_inventory.csv. It reuses the raw JSON already present in data/raw/openaq/; the --refresh option forces a new API call and writes a new raw file (the old one is never overwritten).
"""

import argparse
import csv
import json
import logging
from datetime import date

from pm25 import config, manifest
from pm25.sources import openaq

FIELDS = [
    "location_id", "name", "provider", "owner", "latitude", "longitude",
    "timezone", "is_monitor", "sensor_id", "units",
    "datetime_first_local", "datetime_last_local",
]


def get_locations(refresh: bool):
    """Return (path of the raw file, its content), calling the API only if needed."""
    raw_dir = config.ROOT / config.require("paths.raw") / "openaq"
    existing_files = sorted(raw_dir.glob("locations_*.json"))

    if refresh or len(existing_files) == 0:
        lat, lon = config.require("openaq.search_area.coordinates")
        radius = config.require("openaq.search_area.radius_m")
        payload = openaq.OpenAQ().locations()
        path = openaq.save_raw(
            payload,
            f"locations_coordinates_{lat}_{lon}_r{radius}_{date.today()}.json",
            "openaq-v3-locations",
            f"GET /locations coordinates={lat},{lon} radius={radius}",
        )
    else:
        path = existing_files[-1]
        payload = json.loads(path.read_text(encoding="utf-8"))
        manifest.register(path, "openaq-v3-locations", "raw response already present")
    return path, payload


def local_time_or_none(period):
    """`datetimeFirst` / `datetimeLast` can be null in the API response."""
    if period is None:
        return None
    return period.get("local")


def main(refresh: bool) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    path, payload = get_locations(refresh)
    print(f"source: {path.name} ({payload['meta']['found']} stations found)")

    rows = []
    for location, sensor in openaq.pm25_sensors(payload["results"]):
        rows.append({
            "location_id": location["id"],
            "name": location["name"],
            "provider": location["provider"]["name"],
            "owner": location["owner"]["name"],
            "latitude": location["coordinates"]["latitude"],
            "longitude": location["coordinates"]["longitude"],
            "timezone": location["timezone"],
            "is_monitor": location["isMonitor"],
            "sensor_id": sensor["id"],
            "units": sensor["parameter"]["units"],
            "datetime_first_local": local_time_or_none(location["datetimeFirst"]),
            "datetime_last_local": local_time_or_none(location["datetimeLast"]),
        })
    rows.sort(key=lambda row: row["location_id"])

    out = config.path("interim") / "stations_inventory.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    units = set()
    timezones = set()
    monitors = 0
    without_period = 0
    for row in rows:
        units.add(row["units"])
        timezones.add(row["timezone"])
        if row["is_monitor"]:
            monitors = monitors + 1
        if not row["datetime_first_local"]:
            without_period = without_period + 1

    print(f"{len(rows)} PM2.5 sensors (fixed stations) -> {out}")
    print(f"  units          : {sorted(units)}")
    print(f"  time zones     : {sorted(timezones)}")
    print(f"  monitors       : {monitors}/{len(rows)}")
    print(f"  without period : {without_period} (to ask sensor by sensor, see scripts/02)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="call the API again")
    args = parser.parse_args()
    main(args.refresh)
