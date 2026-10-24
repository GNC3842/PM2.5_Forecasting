import pytest

from pm25 import config

CFG = {"a": {"b": 1, "vide": None}, "liste": [1, 2]}


def test_reading_imbricated_keys():
    assert config.require("a.b", CFG) == 1


def test_that_fails_when_value_is_none():
    with pytest.raises(ValueError, match="a.vide : no decision yet"):
        config.require("a.vide", CFG)


def test_that_fails_when_key_is_missing():
    with pytest.raises(KeyError):
        config.require("a.unknown", CFG)
    with pytest.raises(KeyError):
        config.require("liste.0", CFG)


def test_reading_real_config():
    cfg = config.load()
    assert config.require("timezone", cfg) == "Asia/Bangkok" 
    assert config.require("forecast.horizon_days", cfg) == 1
    with pytest.raises(ValueError):
        config.require("forecast.emission_hour", cfg)


def test_that_fails_when_secret_is_missing():
    with pytest.raises(KeyError):
        config.secret("MISSING_ENV_VAR")
