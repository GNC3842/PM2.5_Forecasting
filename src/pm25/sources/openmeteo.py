"""Open-Meteo Historical Weather API: one raw CSV per station and per model.

Facts checked on 2026-10-23 on the real API (see `docs/sources/openmeteo.md`):

- `models=era5_land` only serves temperature, humidity and dew point in Hanoi:
  wind, precipitation, pressures and clouds are all null. Model rejected.
- `boundary_layer_height` is served by no model of the archive.
- `era5` was served until 2026-10-18T06:00 (5 days late); `ecmwf_ifs`
  until the current hour.
- `models` is mandatory here: the default `best_match` mixes IFS and ERA5 and gives
  a non-homogeneous series, useless to train and then run a model.
"""

import logging
import time
from datetime import date
from pathlib import Path

import requests

from .. import config, manifest

log = logging.getLogger(__name__)
MAX_ATTEMPTS = 5

# requests sent during the last minute, as [time, weight] pairs
_budget = []


def cost(start: str, end: str, n_hourly: int) -> float:
    """Fractional cost of one archive request, counted in "calls".

    Measured on 2026-10-23: 9 requests of 10 variables, 603 days/14 in total,
    triggered an HTTP 429 while the announced limit is 600 calls/minute. The cost is
    therefore proportional to the requested duration (14 days per call) and to the
    number of variables above 10. No I/O.
    """
    days = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    days_per_call = config.require("openmeteo.days_per_call")
    return max(1.0, days / days_per_call) * max(1.0, n_hourly / 10)


def _throttle(weight: float) -> None:
    """Wait until the total weight of the last minute leaves room for `weight`."""
    limit = config.require("openmeteo.calls_per_minute")
    while True:
        now = time.monotonic()

        # forget the requests older than one minute
        while len(_budget) > 0 and now - _budget[0][0] >= 60:
            _budget.pop(0)

        used = 0.0
        for sent_time, sent_weight in _budget:
            used = used + sent_weight

        # a request heavier than the limit still goes through when nothing else is waiting
        if used + weight <= limit or len(_budget) == 0:
            _budget.append([now, weight])
            return

        wait = 60 - (now - _budget[0][0]) + 0.5
        log.info("Open-Meteo budget reached: waiting %.0f s", wait)
        time.sleep(wait)


def window(start: str, end: str, model: str, today: str):
    """Period to ask for one model, as (start, end), or `None` if it is empty.

    Cut at the first day the model is served (`openmeteo.model_start`) and at today:
    `ecmwf_ifs` only starts in 2017 and the archive refuses a future date.
    No I/O, tested without network.
    """
    model_start = str(config.require("openmeteo.model_start")[model])
    first_day = max(start, model_start)
    last_day = min(end, today)
    if first_day > last_day:
        return None
    return (first_day, last_day)


def fetch_csv(lat: float, lon: float, start: str, end: str, model: str) -> str:
    """One archive request, CSV format, timestamps in Asia/Bangkok.

    The rate is spread according to the weight of the requests, not their number:
    an 8-year request alone weighs a third of the budget of one minute.
    """
    hourly = config.require("openmeteo.hourly")
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "hourly": ",".join(hourly),
        "timezone": config.require("timezone"),
        "wind_speed_unit": config.require("openmeteo.wind_speed_unit"),
        "models": model,
        "format": "csv",
    }
    weight = cost(start, end, len(hourly))

    for attempt in range(1, MAX_ATTEMPTS + 1):
        _throttle(weight)
        response = requests.get(config.require("openmeteo.archive_url"), params=params, timeout=180)
        log.info("GET archive %s %s..%s (%s,%s) weight %.0f -> %s",
                 model, start, end, lat, lon, weight, response.status_code)

        if response.status_code == 429 or response.status_code >= 500:
            _budget.clear()  # the real budget is used up: start again from a full minute
            log.warning("%s on Open-Meteo: waiting 61 s (attempt %d)", response.status_code, attempt)
            time.sleep(61)
            continue

        response.raise_for_status()
        return response.text

    raise RuntimeError(f"still failing on the Open-Meteo archive {model} {start}..{end}")


def save_raw(csv_text: str, name: str, note: str = "") -> Path:
    out = config.ROOT / config.require("paths.raw") / "openmeteo" / name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(csv_text, encoding="utf-8")
    manifest.register(out, "open-meteo-archive", note)
    return out
