"""
EPA AQI category for a given PM2.5 concentration.

Tresholds are define in `config/config.yaml with the the param `aqi.breakpoints`, these values come from the EPA fact sheet of February 2024.
"""

from __future__ import annotations

from . import config


def aqi_category(value: float) -> str:
    """EPA AQI category for a given PM2.5 concentration."""
    if not value >= 0:
        raise ValueError(f"{value} : PM2.5 concentration must be non-negative")
    for upper, name in config.require("aqi.breakpoints"):
        if value <= upper:
            return name
    raise ValueError(f"{value} : exceeds the highest threshold in aqi.breakpoints")
