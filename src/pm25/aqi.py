"""
EPA AQI category for a given PM2.5 concentration.

Thresholds are defined in `config/config.yaml` under `aqi.breakpoints`. They come from the EPA fact sheet of February 2024.
"""

from . import config


def aqi_category(value: float) -> str:
    """EPA AQI category for a given PM2.5 concentration."""
    # written "not >= 0" on purpose: NaN gives False to every comparison, so it is rejected too
    if not value >= 0:
        raise ValueError(f"{value} : PM2.5 concentration must be non-negative")
    for upper, name in config.require("aqi.breakpoints"):
        if value <= upper:
            return name
    raise ValueError(f"{value} : exceeds the highest threshold in aqi.breakpoints")
