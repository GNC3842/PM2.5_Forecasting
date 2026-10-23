"""Accès aux paramètres de `config/config.yaml` et aux secrets de `.env`.

Pour rappel un paramètre `null` est une décision non prise. `require()` échoue
au lieu de substituer un défaut.
"""

from __future__ import annotations

import os
import re
from functools import cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "config.yaml"
ENV_PATH = ROOT / ".env"

_ENV_LINE = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*[:=]\s*(.*?)\s*$")


@cache
def load(path: Path | None = None): -> dict[str, Any]:
    """
    Charge et met en cache le fichier de configuration YAML pour éviter de le relire à chaque appel
    Args:
        Prends un cheminoptionnel vers un fichier de config YAML et sinon chemin par défaut utilisé
    Returns:
        Un dictionnaire contenant les paramètres de configuration
    """
    return yaml.safe_load((path or CONFIG_PATH).read_text(encoding="utf-8"))


def require(dotted: str, config: dict[str, Any] | None = None) -> Any:
    """Lit `a.b.c`. Échoue si la clé est absente ou si sa valeur est `null`."""
    node: Any = load() if config is None else config
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(f"{dotted} : clé absente de la configuration")
        node = node[part]
    if node is None:
        raise ValueError(f"{dotted} : décision non prise (null dans config.yaml)")
    return node


def path(name: str) -> Path:
    """Chemin absolu d'un dossier de `paths`, créé s'il manque (sauf raw/external)."""
    p = ROOT / require(f"paths.{name}")
    if name in {"interim", "processed"}:
        p.mkdir(parents=True, exist_ok=True)
    return p


def secret(env_var: str) -> str:
    """Secret depuis l'environnement, sinon depuis `.env`. Jamais affiché ni journalisé."""
    if value := os.environ.get(env_var):
        return value
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if line.lstrip().startswith("#"):
                continue
            if (m := _ENV_LINE.match(line)) and m[1] == env_var:
                return m[2].strip("\"'")
    raise KeyError(f"{env_var} absent de l'environnement et de .env")
