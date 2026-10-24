"""Open-Meteo period bounds and request cost: no network call."""

import pytest

from pm25.sources import openmeteo

TODAY = "2026-10-23"


PARAMS = {
    "openmeteo.model_start": {"era5": "1940-01-01", "ecmwf_ifs": "2017-01-01"},
    "openmeteo.days_per_call": 14,
    "openmeteo.calls_per_minute": 550,
}


@pytest.fixture(autouse=True)
def fake_params(monkeypatch):
    def fake_require(key, config=None):
        return PARAMS[key]

    monkeypatch.setattr(openmeteo.config, "require", fake_require)


def test_period_unchanged_if_fully_served():
    assert openmeteo.window("2024-01-29", "2026-10-21", "era5", TODAY) == (
        "2024-01-29", "2026-10-21")


def test_start_cut_at_model_service_start():
    # the longest PM2.5 series starts in 2016, before ecmwf_ifs
    assert openmeteo.window("2016-01-30", "2016-11-09", "era5", TODAY) == (
        "2016-01-30", "2016-11-09")
    assert openmeteo.window("2016-11-10", "2025-04-09", "ecmwf_ifs", TODAY) == (
        "2017-01-01", "2025-04-09")


def test_period_fully_before_the_model_gives_none():
    assert openmeteo.window("2016-01-30", "2016-11-09", "ecmwf_ifs", TODAY) is None


def test_end_cut_at_today():
    assert openmeteo.window("2026-01-01", "2027-06-01", "era5", TODAY) == (
        "2026-01-01", TODAY)


def test_one_day_period_is_valid():
    assert openmeteo.window("2024-01-15", "2024-01-15", "era5", TODAY) == (
        "2024-01-15", "2024-01-15")


def test_cost_is_at_least_one_call():
    assert openmeteo.cost("2024-01-01", "2024-01-01", 10) == 1.0
    assert openmeteo.cost("2024-01-01", "2024-01-14", 10) == 1.0


def test_cost_proportional_to_duration():
    assert openmeteo.cost("2024-01-01", "2024-01-28", 10) == 2.0   # 28 d = 2 x 14
    assert openmeteo.cost("2024-01-01", "2024-02-11", 10) == 3.0   # 42 d = 3 x 14


def test_cost_proportional_to_variables_above_ten():
    assert openmeteo.cost("2024-01-01", "2024-01-28", 20) == 4.0   # 2 x 2
    assert openmeteo.cost("2024-01-01", "2024-01-28", 5) == 2.0    # no discount below 10


def test_cost_reproduces_the_observed_429():
    """The 9 requests that triggered the 429 of 2026-10-23 are indeed above 600."""
    periods = [("2016-01-30", "2016-11-09"), ("2016-11-10", "2025-04-09"),
               ("2017-01-01", "2025-04-09"), ("2019-11-28", "2020-06-23"),
               ("2019-11-28", "2020-06-23"), ("2024-01-29", "2025-06-10"),
               ("2024-01-29", "2025-06-10"), ("2024-01-22", "2024-12-11"),
               ("2024-01-22", "2024-12-11")]
    total = 0.0
    for start, end in periods:
        total = total + openmeteo.cost(start, end, 10)
    assert total > 600


def test_throttle_waits_when_the_budget_is_exceeded(monkeypatch):
    """The first call always goes through; the next one waits if the budget is exceeded."""
    waits = []
    clock = [0.0]

    def fake_sleep(seconds):          # a fake clock must move forward when we sleep
        waits.append(seconds)
        clock[0] = clock[0] + seconds

    def fake_monotonic():
        return clock[0]

    monkeypatch.setattr(openmeteo.time, "sleep", fake_sleep)
    monkeypatch.setattr(openmeteo.time, "monotonic", fake_monotonic)
    openmeteo._budget.clear()
    openmeteo._throttle(500.0)
    assert waits == []                    # budget free
    openmeteo._throttle(500.0)            # 1000 > 550: must wait for the minute
    assert len(waits) == 1 and 59 < waits[0] <= 61
    openmeteo._budget.clear()
