"""
Each downloaded file is written in `data/manifest.csv` with its SHA-256 hash, size, source and a note.

A file already registered with the same hash is not registered again. A different hash for the
same path adds a new line (the history is never overwritten).
"""

import csv
import hashlib
from datetime import date
from pathlib import Path

from . import config

FIELDS = ["date", "path", "sha256", "bytes", "source", "note"]


def sha256(path: Path) -> str:
    """SHA-256 hash of a file, read by blocks of 1 MB so big files fit in memory."""
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(1024 * 1024)
            if not block:
                break
            hasher.update(block)
    return hasher.hexdigest()


def is_empty(manifest: Path) -> bool:
    return not manifest.exists() or manifest.stat().st_size == 0


def read_rows(manifest: Path) -> list:
    if is_empty(manifest):
        return []
    with manifest.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def register(file: Path, source: str, note: str = "") -> str:
    """Add `file` to the manifest and return its SHA-256. Calling it twice does nothing more."""
    manifest = config.ROOT / config.require("paths.manifest")
    relative_path = file.resolve().relative_to(config.ROOT).as_posix()
    digest = sha256(file)

    for row in read_rows(manifest):
        if row["path"] == relative_path and row["sha256"] == digest:
            return digest

    new_row = {
        "date": date.today().isoformat(),
        "path": relative_path,
        "sha256": digest,
        "bytes": str(file.stat().st_size),
        "source": source,
        "note": note,
    }
    # we check the file itself and not the rows: a manifest with only its header
    # has no rows, and the header would be written a second time
    write_header = is_empty(manifest)
    with manifest.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(new_row)
    return digest


def verify() -> list:
    """Problems in the manifest: missing file or different hash. Empty list if everything is fine.

    A path can have several lines (content changed, history kept): only the last one counts.
    """
    manifest = config.ROOT / config.require("paths.manifest")

    # the file is in chronological order, so later lines replace earlier ones
    last_row_of_path = {}
    for row in read_rows(manifest):
        last_row_of_path[row["path"]] = row

    problems = []
    for relative_path, row in last_row_of_path.items():
        file = config.ROOT / relative_path
        if not file.exists():
            problems.append(f"{relative_path} : missing")
            continue
        digest = sha256(file)
        if digest != row["sha256"]:
            problems.append(f"{relative_path} : different hash ({digest[:12]} instead of "
                            f"{row['sha256'][:12]}, registered on {row['date']})")
    return problems
