"""Hourly weather at the coordinates of each station -> data/raw/openmeteo/<model>_<station>.csv.

One request per station and per model (`openmeteo.models`), over the PM2.5 period of the
station, cut at the first day the model is served. A file already on disk is not
downloaded again. The raw Open-Meteo CSV is kept as it is, header included.

The period comes from `data/interim/openaq_coverage.csv` (measured coverage) if it exists,
otherwise from `stations_inventory.csv` (announced period).
"""

import argparse
import csv
import logging
from datetime import date

from pm25 import config
from pm25.sources import openmeteo


def read_csv_by_location(path) -> dict:
    """Rows of a CSV file indexed by `location_id` (the last row wins)."""
    rows = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows[row["location_id"]] = row
    return rows


def get_stations() -> list:
    """One row per station: coordinates and PM2.5 period."""
    interim = config.path("interim")
    inventory = read_csv_by_location(interim / "stations_inventory.csv")

    measured = {}
    coverage_file = interim / "openaq_coverage.csv"
    if coverage_file.exists():
        for location_id, row in read_csv_by_location(coverage_file).items():
            if row["first_local"]:
                measured[location_id] = row

    stations = []
    for location_id, row in inventory.items():
        if location_id in measured:
            first = measured[location_id]["first_local"]
            last = measured[location_id]["last_local"]
            period_source = "measured coverage"
        else:
            first = row["datetime_first_local"]
            last = row["datetime_last_local"]
            period_source = "announced period"

        if not first or not last:
            logging.warning("station %s (%s): no PM2.5 period, skipped", location_id, row["name"])
            continue

        stations.append({
            "location_id": location_id,
            "name": row["name"],
            "lat": float(row["latitude"]),
            "lon": float(row["longitude"]),
            "start": first[:10],
            "end": last[:10],
            "period_source": period_source,
        })

    stations.sort(key=lambda station: int(station["location_id"]))
    return stations


def main(dry_run: bool) -> None:
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(message)s")
    models = config.require("openmeteo.models")
    raw_dir = config.ROOT / config.require("paths.raw") / "openmeteo"
    today = date.today().isoformat()

    jobs = []
    for station in get_stations():
        for model in models:
            period = openmeteo.window(station["start"], station["end"], model, today)
            if period is None:
                logging.warning("%s / %s: PM2.5 period outside the model service, skipped",
                                station["name"], model)
                continue
            job = dict(station)
            job["model"] = model
            job["start"] = period[0]
            job["end"] = period[1]
            job["file_name"] = f"{model}_{station['location_id']}.csv"
            job["exists"] = (raw_dir / job["file_name"]).exists()
            jobs.append(job)

    todo = []
    for job in jobs:
        if not job["exists"]:
            todo.append(job)

    n_hourly = len(config.require("openmeteo.hourly"))
    total_weight = 0.0
    for job in todo:
        total_weight = total_weight + openmeteo.cost(job["start"], job["end"], n_hourly)
    limit = config.require("openmeteo.calls_per_minute")

    print(f"{len(jobs)} files, {len(jobs) - len(todo)} already on disk, {len(todo)} to download")
    print(f"cost: {total_weight:.0f} fractional calls (quota 10 000/day, {limit}/min) "
          f"so at least {total_weight / limit:.0f} min of spreading")

    if dry_run:
        for job in todo:
            print(f"  {job['model']:<10} {job['location_id']:>9} {job['name'][:28]:<28} "
                  f"{job['start']} -> {job['end']}  ({job['period_source']})")
        return

    n = 0
    for job in todo:
        n = n + 1
        text = openmeteo.fetch_csv(job["lat"], job["lon"], job["start"], job["end"], job["model"])
        out = openmeteo.save_raw(
            text, job["file_name"],
            f"{job['model']} {job['start']}..{job['end']} station {job['location_id']} "
            f"({job['lat']},{job['lon']}), {job['period_source']}",
        )
        # the grid cell returned differs from the requested coordinates: we read it in the header
        lines = text.splitlines()
        columns = lines[0].split(",")
        values = lines[1].split(",")
        grid_cell = dict(zip(columns, values))
        print(f"[{n}/{len(todo)}] {job['model']:<10} {job['location_id']:>9} "
              f"{job['name'][:24]:<24} {len(lines) - 4:>6} h  "
              f"grid cell {grid_cell.get('latitude', '?')},{grid_cell.get('longitude', '?')}  "
              f"-> {out.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="only show the plan and the cost")
    args = parser.parse_args()
    main(args.dry_run)
