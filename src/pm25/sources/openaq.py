"""OpenAQ v3 client: key in the header, limited rate, HTTP 429 handled, raw responses saved.

- `datetime_from` / `datetime_to` are **inclusive**; `from` applies to
  `period.datetimeFrom`, `to` to `period.datetimeTo`. Two windows side by side
  (`[A, B]` then `[B, C]`) therefore give no gap and no duplicate.
- a date alone (`2024-06-03`) is read in the local time zone of the station;
  this module only sends explicit UTC instants, so there is no ambiguity.
- the timestamp of an hour marks the end of the interval: attach the hour to a day
  with `period.datetimeFrom.local`.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

from .. import config

log = logging.getLogger(__name__)
UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
MAX_ATTEMPTS = 5


class OpenAQ:
    def __init__(self):
        settings = config.require("openaq")
        self.base = settings["base_url"]
        self.limit = config.require("openaq.page_limit")
        self.delay = config.require("openaq.min_seconds_between_calls")
        self._session = requests.Session()
        self._session.headers["X-API-Key"] = config.secret(settings["api_key_env"])
        self._last_call = 0.0

    def get(self, path: str, **params) -> dict:
        """One GET call, spaced from the previous one, retried on HTTP 429 and on 5xx.

        OpenAQ 5xx errors are temporary (seen on 2026-10-23: a 500 on
        `/sensors/7772068/hours?page=2` answered 200 to the three next tries).
        Without this retry, a download of several hundred requests almost
        always fails along the way.
        """
        for attempt in range(1, MAX_ATTEMPTS + 1):
            seconds_since_last_call = time.monotonic() - self._last_call
            if seconds_since_last_call < self.delay:
                time.sleep(self.delay - seconds_since_last_call)
            self._last_call = time.monotonic()

            response = self._session.get(self.base + path, params=params, timeout=60)
            log.info("GET %s %s -> %s", path, params, response.status_code)

            if response.status_code == 429:
                reset = float(response.headers.get("x-ratelimit-reset", 60)) + 1
                log.warning("429 on %s: waiting %.0f s (attempt %d)", path, reset, attempt)
                time.sleep(reset)
                continue

            if response.status_code >= 500:
                pause = 2.0 * attempt
                log.warning("%s on %s %s: waiting %.0f s (attempt %d)",
                            response.status_code, path, params, pause, attempt)
                time.sleep(pause)
                continue

            response.raise_for_status()
            return response.json()

        raise RuntimeError(f"still failing on {path} {params} after {MAX_ATTEMPTS} attempts")

    def pages(self, path: str, **params) -> list:
        """Ask every page until the end: an empty or incomplete page is the last one.

        Returns a list of pages, each page being a list of results.
        """
        all_pages = []
        page = 1
        while True:
            payload = self.get(path, limit=self.limit, page=page, **params)
            results = payload["results"]
            if len(results) > 0:
                all_pages.append(results)
            if len(results) < self.limit:
                return all_pages
            page = page + 1

    def locations(self) -> dict:
        lat, lon = config.require("openaq.search_area.coordinates")
        return self.get(
            "/locations",
            coordinates=f"{lat},{lon}",
            radius=config.require("openaq.search_area.radius_m"),
            limit=self.limit,
        )

    def hours(self, sensor_id: int, start: datetime, end: datetime) -> list:
        """Every hour of `[start, end]` for one sensor, asked by windows side by side."""
        window = timedelta(days=config.require("openaq.window_days"))
        all_hours = []
        window_start = start
        while window_start < end:
            window_end = window_start + window
            if window_end > end:
                window_end = end

            pages = self.pages(
                f"/sensors/{sensor_id}/hours",
                datetime_from=window_start.strftime(UTC_FORMAT),
                datetime_to=window_end.strftime(UTC_FORMAT),
            )
            for page in pages:
                all_hours.extend(page)

            window_start = window_end
        return dedupe(all_hours)


def dedupe(rows: list) -> list:
    """Keep one row per `period.datetimeFrom.utc`, sorted. Protects against overlapping windows."""
    row_by_start = {}
    for row in rows:
        start = row["period"]["datetimeFrom"]["utc"]
        row_by_start[start] = row

    result = []
    for start in sorted(row_by_start):
        result.append(row_by_start[start])
    return result


def coverage_pct(hours_valid: int, span_hours: int) -> float:
    """Share of the period covered by **usable** hours, in percent.

    Dividing `hours_total` by `span_hours` would overestimate the coverage: the API
    also returns `null` hours and sentinels (sensor 21632: 89.7 % instead of 77.8 %).
    """
    if span_hours == 0:
        return 0.0
    return round(100 * hours_valid / span_hours, 1)


def coverage(hours: list, span_hours: int, sentinels: set) -> dict:
    """**Measured** coverage of an hourly series. No I/O.

    `hours_total` counts the hours returned, `hours_valid` the usable ones:
    neither `null` nor sentinel. They differ, and `hours_valid` is the one that decides
    whether a day is valid (`forecast.min_valid_hours_per_day`), so it is the one
    `coverage_pct` divides by `span_hours`.
    """
    null_count = 0
    sentinel_count = 0
    for hour in hours:
        value = hour["value"]
        if value is None:
            null_count = null_count + 1
        elif value in sentinels:
            sentinel_count = sentinel_count + 1
    valid_count = len(hours) - null_count - sentinel_count

    first_local = ""
    last_local = ""
    if len(hours) > 0:
        first_local = hours[0]["period"]["datetimeFrom"]["local"]
        last_local = hours[-1]["period"]["datetimeFrom"]["local"]

    return {
        "hours_total": len(hours),
        "hours_valid": valid_count,
        "hours_null": null_count,
        "hours_sentinel": sentinel_count,
        "span_hours": span_hours,
        "coverage_pct": coverage_pct(valid_count, span_hours),
        "first_local": first_local,
        "last_local": last_local,
    }


def pm25_sensors(locations: list) -> list:
    """List of (station, sensor) pairs, for every PM2.5 sensor of the **fixed** stations."""
    pairs = []
    for location in locations:
        if location["isMobile"]:
            continue
        for sensor in location["sensors"]:
            if sensor["parameter"]["name"] == "pm25":
                pairs.append((location, sensor))
    return pairs


def save_raw(payload, name: str, source: str, note: str = "", indent=1) -> Path:
    """Write a raw response in `data/raw/openaq/` and register it in the manifest.

    `indent=None` for the big hour files: indentation triples their size
    without adding anything, the content is the same.
    """
    from .. import manifest

    out = config.ROOT / config.require("paths.raw") / "openaq" / name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=indent), encoding="utf-8")
    manifest.register(out, source, note)
    return out
