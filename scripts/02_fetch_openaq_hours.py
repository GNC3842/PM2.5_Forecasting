"""Hourly PM2.5 of every sensor of the inventory -> data/raw/openaq/hours_<sensor>.json.

The real period is read from `GET /v3/sensors/{id}`: the `/locations` response leaves it
out for some stations. A file already on disk is never downloaded again, so the
script can be restarted after an interruption, a 429 or a persistent 5xx.

Then writes `data/interim/openaq_coverage.csv`: the **measured** coverage of each
sensor, read again from `data/raw/` and not from the current session (a restart does
not lose the coverage of the sensors already downloaded). It is the only basis to
decide the inclusion thresholds of the stations (step 3).
"""

import argparse
import csv
import json
import logging
from datetime import datetime, timedelta, timezone

from pm25 import config
from pm25.sources import openaq

COVERAGE_FIELDS = [
    "sensor_id", "location_id", "name", "hours_total", "hours_valid",
    "hours_null", "hours_sentinel", "span_hours", "coverage_pct",
    "first_local", "last_local",
]


def hours_between(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() // 3600)


def sensor_period(client: openaq.OpenAQ, sensor_id: int):
    """Period served by a sensor, according to the API and not to the inventory.

    Returns (start, end) in UTC, or None if the API gives no period.
    """
    sensor = client.get(f"/sensors/{sensor_id}")["results"][0]
    first = sensor.get("datetimeFirst")
    last = sensor.get("datetimeLast")
    if not first or not last:
        logging.warning("sensor %s: no period served", sensor_id)
        return None
    # The bounds are inclusive and apply to the period bounds: we widen by one
    # hour on each side so we lose neither the first nor the last hour.
    start = datetime.fromisoformat(first["utc"]) - timedelta(hours=1)
    end = datetime.fromisoformat(last["utc"]) + timedelta(hours=1)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def get_periods(client: openaq.OpenAQ, sensor_ids: list) -> dict:
    """Period of each sensor; sensors without a period are left out."""
    periods = {}
    for sensor_id in sensor_ids:
        period = sensor_period(client, sensor_id)
        if period is not None:
            periods[sensor_id] = period
    return periods


def download(client: openaq.OpenAQ, sensor_ids: list, stations: dict) -> None:
    periods = get_periods(client, sensor_ids)
    n = 0
    for sensor_id, (start, end) in periods.items():
        n = n + 1
        hours = client.hours(sensor_id, start, end)
        span_hours = hours_between(start, end)
        content = {
            "sensor_id": sensor_id,
            "location_id": int(stations[sensor_id]["location_id"]),
            "datetime_from": start.isoformat(),
            "datetime_to": end.isoformat(),
            "results": hours,
        }
        openaq.save_raw(
            content,
            f"hours_{sensor_id}.json",
            "openaq-v3-sensors-hours",
            f"{len(hours)} hours out of {span_hours} expected",
            indent=None,
        )
        name = stations[sensor_id]["name"][:28]
        print(f"[{n}/{len(periods)}] {sensor_id:>9} {name:<28} {len(hours):>6} h / {span_hours:>6}")


def measure_coverage(sensor_ids: list, stations: dict) -> list:
    """Read `data/raw/openaq/hours_*.json` again and measure the coverage of each sensor."""
    raw_dir = config.ROOT / config.require("paths.raw") / "openaq"
    sentinels = set(config.require("openaq.sentinel_values"))
    rows = []
    for sensor_id in sensor_ids:
        file = raw_dir / f"hours_{sensor_id}.json"
        if not file.exists():
            continue
        data = json.loads(file.read_text(encoding="utf-8"))
        # the requested window is read from the file: the coverage depends neither
        # on a network call nor on the session that downloaded it
        start = datetime.fromisoformat(data["datetime_from"])
        end = datetime.fromisoformat(data["datetime_to"])

        row = {
            "sensor_id": sensor_id,
            "location_id": data["location_id"],
            "name": stations[sensor_id]["name"],
        }
        row.update(openaq.coverage(data["results"], hours_between(start, end), sentinels))
        rows.append(row)

    rows.sort(key=lambda row: row["hours_valid"], reverse=True)
    return rows


def print_plan(client: openaq.OpenAQ, todo: list, stations: dict) -> None:
    """Dry run: show what would be downloaded and how many requests it costs."""
    periods = get_periods(client, todo)
    total_hours = 0
    for start, end in periods.values():
        total_hours = total_hours + hours_between(start, end)
    max_requests = total_hours / config.require("openaq.page_limit") + 2 * len(periods)
    print(f"{total_hours} hours to cover, so at most {max_requests:.0f} requests")

    sorted_ids = sorted(periods, key=lambda sensor_id: periods[sensor_id][0])
    for sensor_id in sorted_ids:
        start, end = periods[sensor_id]
        name = stations[sensor_id]["name"][:34]
        print(f"  {sensor_id:>9} {name:<34} {start:%Y-%m-%d} -> {end:%Y-%m-%d} "
              f"({(end - start).days} d)")


def main(only, dry_run: bool) -> None:
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(message)s")
    stations = {}
    with (config.path("interim") / "stations_inventory.csv").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            stations[int(row["sensor_id"])] = row

    wanted = []
    for sensor_id in stations:
        if only is None or sensor_id in only:
            wanted.append(sensor_id)

    raw_dir = config.ROOT / config.require("paths.raw") / "openaq"
    todo = []
    for sensor_id in wanted:
        if not (raw_dir / f"hours_{sensor_id}.json").exists():
            todo.append(sensor_id)
    print(f"{len(wanted)} sensors asked, {len(wanted) - len(todo)} already on disk, "
          f"{len(todo)} to download")

    # no client (so no key needed) when there is nothing to download: the coverage
    # is computed again from `data/raw/` only
    client = None
    if len(todo) > 0 or dry_run:
        client = openaq.OpenAQ()

    if dry_run:
        print_plan(client, todo, stations)
        return

    if len(todo) > 0:
        download(client, todo, stations)

    rows = measure_coverage(wanted, stations)
    out = config.path("interim") / "openaq_coverage.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, COVERAGE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    total_valid = 0
    total_null = 0
    total_sentinel = 0
    one_year_or_more = 0
    for row in rows:
        total_valid = total_valid + row["hours_valid"]
        total_null = total_null + row["hours_null"]
        total_sentinel = total_sentinel + row["hours_sentinel"]
        if row["hours_valid"] >= 8760:
            one_year_or_more = one_year_or_more + 1

    print(f"\n{len(rows)} sensors measured, {total_valid} valid hours in total -> {out}")
    print(f"  null hours     : {total_null}")
    print(f"  sentinel hours : {total_sentinel}")
    print(f"  >= 8 760 valid hours (1 year) : {one_year_or_more} sensors")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", type=int, nargs="+", metavar="SENSOR_ID")
    parser.add_argument("--dry-run", action="store_true", help="only show the plan and the cost")
    args = parser.parse_args()
    main(args.only, args.dry_run)
