import pytest

from pm25 import aqi


@pytest.mark.parametrize(
    "value,expected",
    [
        (0.0, "Good"),
        (9.0, "Good"),
        (9.1, "Moderate"),
        (35.4, "Moderate"),
        (35.5, "Unhealthy for Sensitive Groups"),
        (55.4, "Unhealthy for Sensitive Groups"),
        (55.5, "Unhealthy"),
        (125.4, "Unhealthy"),
        (125.5, "Very Unhealthy"),
        (225.4, "Very Unhealthy"),
        (225.5, "Hazardous"),
        (975.0, "Hazardous"),
    ],
)
def test_category_for_each_bound(value, expected):
    assert aqi.aqi_category(value) == expected


def test_that_a_negative_value_is_rejected():
    with pytest.raises(ValueError):
        aqi.aqi_category(-1.0)
    with pytest.raises(ValueError):
        aqi.aqi_category(-9999.0)


def test_that_a_non_numeric_value_is_rejected():
    with pytest.raises(ValueError):
        aqi.aqi_category(float("nan"))
