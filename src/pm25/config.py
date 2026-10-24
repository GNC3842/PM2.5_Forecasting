"""Read the parameters of `config/config.yaml` and the secrets of `.env`.

A parameter set to `null` is a decision not taken yet: `require()` raises an
error instead of using a default value.
"""

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "config.yaml"
ENV_PATH = ROOT / ".env"


def load(path=None) -> dict:
    """Read the YAML config file and return it as a dictionary.
    If no path is given, `config/config.yaml` is used.
    """
    if path is None:
        path = CONFIG_PATH
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text)


def require(dotted: str, config: dict = None):
    """Read a key written like `a.b.c`.
    Raises KeyError if the key does not exist, ValueError if its value is `null`.
    """
    if config is None:
        config = load()
    node = config
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(f"{dotted} : key missing from the configuration")
        node = node[part]

    if node is None:
        raise ValueError(f"{dotted} : no decision yet (null in config.yaml)")
    return node


def path(name: str) -> Path:
    """Absolute path of a folder listed in `paths`.
    `interim` and `processed` are created if missing; raw and external are never created.
    """
    folder = ROOT / require("paths." + name)
    if name == "interim" or name == "processed":
        folder.mkdir(parents=True, exist_ok=True)
    return folder


def secret(env_var: str) -> str:
    """Read a secret from the environment, or else from `.env`. Never print it."""
    value = os.environ.get(env_var)
    if value:
        return value
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
        for line in lines:
            line = line.strip()
            if line == "" or line.startswith("#"):
                continue

            # the key and the value are separated by the first "=" or ":"
            separator_index = -1
            for i in range(len(line)):
                if line[i] == "=" or line[i] == ":":
                    separator_index = i
                    break
            if separator_index == -1:
                continue

            key = line[:separator_index].strip()
            value = line[separator_index + 1:].strip()
            value = value.strip("\"'")
            if key == env_var:
                return value

    raise KeyError(f"{env_var} not found in the environment nor in .env")
