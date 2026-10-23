"""Inscription des fichiers téléchargés dans `data/manifest.csv` (SHA-256).

Un fichier déjà inscrit avec la même empreinte n'est pas réinscrit ; une empreinte
différente pour le même chemin ajoute une ligne (l'historique n'est jamais réécrit).
"""

from __future__ import annotations

import csv
import hashlib
from datetime import date
from pathlib import Path

from . import config

FIELDS = ["date", "path", "sha256", "bytes", "source", "note"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def _rows(manifest: Path) -> list[dict[str, str]]:
    if not manifest.exists() or manifest.stat().st_size == 0:
        return []
    with manifest.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def register(file: Path, source: str, note: str = "") -> str:
    """Ajoute `file` au manifeste et renvoie son SHA-256. Idempotent."""
    manifest = config.ROOT / config.require("paths.manifest")
    rel = file.resolve().relative_to(config.ROOT).as_posix()
    digest = sha256(file)
    rows = _rows(manifest)
    if any(r["path"] == rel and r["sha256"] == digest for r in rows):
        return digest
    new = {
        "date": date.today().isoformat(),
        "path": rel,
        "sha256": digest,
        "bytes": str(file.stat().st_size),
        "source": source,
        "note": note,
    }
    with manifest.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS)
        if not rows:
            w.writeheader()
        w.writerow(new)
    return digest
