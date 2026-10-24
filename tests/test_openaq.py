"""OpenAQ client: fake responses that follow the documented schema, no network call."""

from datetime import datetime, timedelta, timezone

import pytest

from pm25.sources import openaq


def utc_and_local(moment: datetime) -> dict:
    return {
        "utc": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "local": moment.astimezone(timezone(timedelta(hours=7))).isoformat(),
    }


def make_hour(start_utc: str) -> dict:
    """One hourly object, with the schema of /v3/sensors/{id}/hours."""
    start = datetime.fromisoformat(start_utc).replace(tzinfo=timezone.utc)
    end = start + timedelta(hours=1)
    return {
        "value": 42.0,
        "flagInfo": {"hasFlags": False},
        "parameter": {"id": 2, "name": "pm25", "units": "µg/m³"},
        "period": {"label": "1hour", "interval": "01:00:00",
                   "datetimeFrom": utc_and_local(start), "datetimeTo": utc_and_local(end)},
        "coverage": {"expectedCount": 1, "observedCount": 1, "percentCoverage": 100.0},
        "summary": {"min": 42.0, "avg": 42.0, "max": 42.0},
    }


class FakeClient(openaq.OpenAQ):
    """A client whose `get` serves fake hours and remembers the requests sent."""

    def __init__(self, hours_per_page=None):
        self.base = "https://example.invalid/v3"
        self.limit = 3
        self.delay = 0.0
        self._last_call = 0.0
        self.calls = []
        if hours_per_page is None:
            hours_per_page = {1: 3, 2: 1}
        self.hours_per_page = hours_per_page

    def get(self, path, **params):
        call = {"path": path}
        call.update(params)
        self.calls.append(call)

        page = params.get("page", 1)
        n = self.hours_per_page.get(page, 0)
        start = datetime.fromisoformat(params["datetime_from"].replace("Z", "+00:00"))
        offset = (page - 1) * self.limit
        results = []
        for i in range(n):
            moment = start + timedelta(hours=offset + i)
            results.append(make_hour(moment.strftime("%Y-%m-%dT%H:%M:%S")))
        return {"meta": {"found": n}, "results": results}


class FakeResponse:
    def __init__(self, code, payload=None):
        self.status_code = code
        self.headers = {"x-ratelimit-reset": "0"}
        if payload is None:
            payload = {"meta": {}, "results": []}
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"unexpected raise_for_status ({self.status_code})")


def client_with_codes(monkeypatch, codes):
    """A real OpenAQ client whose session returns the given HTTP codes, without waiting."""

    def fake_require(key, config=None):
        if key == "openaq":
            return {"base_url": "https://example.invalid/v3", "api_key_env": "X"}
        return 0

    def fake_session_get(*args, **kwargs):
        return FakeResponse(remaining_codes.pop(0))

    monkeypatch.setattr(openaq.config, "require", fake_require)
    monkeypatch.setattr(openaq.config, "secret", lambda name: "fake-key")
    monkeypatch.setattr(openaq.time, "sleep", lambda seconds: None)
    client = openaq.OpenAQ()
    remaining_codes = list(codes)
    client._session.get = fake_session_get
    return client


def fake_window_days(monkeypatch, days):
    def fake_require(key, config=None):
        if key == "openaq.window_days":
            return days
        return None

    monkeypatch.setattr(openaq.config, "require", fake_require)


def test_retry_on_500_then_success(monkeypatch):
    client = client_with_codes(monkeypatch, [500, 503, 200])
    assert client.get("/x") == {"meta": {}, "results": []}


def test_retry_on_429_then_success(monkeypatch):
    client = client_with_codes(monkeypatch, [429, 200])
    assert client.get("/x") == {"meta": {}, "results": []}


def test_fails_after_five_attempts(monkeypatch):
    client = client_with_codes(monkeypatch, [500] * 5)
    with pytest.raises(RuntimeError, match="after 5 attempts"):
        client.get("/x")


def test_dedupe_keeps_one_row_per_period_start_and_sorts():
    a = make_hour("2024-02-10T01:00:00")
    b = make_hour("2024-02-10T00:00:00")
    starts = [row["period"]["datetimeFrom"]["utc"] for row in openaq.dedupe([a, b, a])]
    assert starts == ["2024-02-10T00:00:00Z", "2024-02-10T01:00:00Z"]


def test_coverage_separates_returned_hours_from_usable_hours():
    hours = [make_hour("2024-02-10T00:00:00"), make_hour("2024-02-10T01:00:00"),
             make_hour("2024-02-10T02:00:00"), make_hour("2024-02-10T03:00:00")]
    hours[1]["value"] = None
    hours[2]["value"] = -9999.0
    c = openaq.coverage(hours, span_hours=8, sentinels={-9999.0})
    assert c["hours_total"] == 4          # returned by the API
    assert c["hours_valid"] == 2          # neither null nor sentinel
    assert (c["hours_null"], c["hours_sentinel"]) == (1, 1)
    # the coverage uses the usable hours, not the returned hours:
    # 2 valid hours out of 8 expected, not 4/8
    assert c["coverage_pct"] == 25.0
    assert c["first_local"].startswith("2024-02-10T07:00")  # UTC+7


def test_coverage_pct_gives_the_control_value_of_sensor_21632():
    """External check of 2026-10-24: 57 393 valid h / 73 751 expected h = 77.8 %."""
    assert openaq.coverage_pct(hours_valid=57393, span_hours=73751) == 77.8


def test_coverage_of_an_empty_series():
    c = openaq.coverage([], span_hours=0, sentinels={-9999.0})
    assert (c["hours_total"], c["hours_valid"], c["coverage_pct"]) == (0, 0, 0.0)
    assert c["first_local"] == c["last_local"] == ""


def test_pm25_sensors_skips_mobile_stations_and_other_parameters():
    locations = [
        {"id": 1, "isMobile": False, "sensors": [
            {"id": 11, "parameter": {"name": "pm25"}},
            {"id": 12, "parameter": {"name": "no2"}}]},
        {"id": 2, "isMobile": True, "sensors": [{"id": 21, "parameter": {"name": "pm25"}}]},
        {"id": 3, "isMobile": False, "sensors": []},
    ]
    pairs = [(location["id"], sensor["id"]) for location, sensor in openaq.pm25_sensors(locations)]
    assert pairs == [(1, 11)]


def test_paging_stops_on_an_incomplete_page():
    client = FakeClient(hours_per_page={1: 3, 2: 3, 3: 1})
    pages = client.pages("/sensors/1/hours", datetime_from="2024-02-10T00:00:00Z")
    assert [len(page) for page in pages] == [3, 3, 1]
    assert [call["page"] for call in client.calls] == [1, 2, 3]


def test_windows_side_by_side_without_gap_or_overlap(monkeypatch):
    """The bounds are inclusive, so the `to` of a window must be the `from` of the next one."""
    fake_window_days(monkeypatch, 2)
    client = FakeClient(hours_per_page={1: 1})
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    client.hours(1, start, start + timedelta(days=5))
    bounds = [(call["datetime_from"], call["datetime_to"]) for call in client.calls]
    assert bounds == [
        ("2024-01-01T00:00:00Z", "2024-01-03T00:00:00Z"),
        ("2024-01-03T00:00:00Z", "2024-01-05T00:00:00Z"),
        ("2024-01-05T00:00:00Z", "2024-01-06T00:00:00Z"),
    ]
    # no gap: each end is the next start; no duplicate: bounds are inclusive
    for i in range(len(bounds) - 1):
        assert bounds[i][1] == bounds[i + 1][0]


def test_last_window_does_not_go_past_the_requested_end(monkeypatch):
    fake_window_days(monkeypatch, 365)
    client = FakeClient(hours_per_page={1: 1})
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=10)
    client.hours(1, start, end)
    assert client.calls[-1]["datetime_to"] == "2024-01-11T00:00:00Z"


def test_sent_instants_are_always_explicit_utc(monkeypatch):
    """A date alone would be read in the time zone of the station: ambiguity not allowed."""
    fake_window_days(monkeypatch, 365)
    client = FakeClient(hours_per_page={1: 1})
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    client.hours(1, start, start + timedelta(days=1))
    for call in client.calls:
        assert call["datetime_from"].endswith("Z") and "T" in call["datetime_from"]
        assert call["datetime_to"].endswith("Z") and "T" in call["datetime_to"]
