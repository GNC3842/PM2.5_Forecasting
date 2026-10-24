import csv
import pytest
from pm25 import config, manifest


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A fake repository: ROOT redirected, minimal config.yaml."""
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "config.yaml").write_text(
        "paths:\n  manifest: data/manifest.csv\n", encoding="utf-8"
    )
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config" / "config.yaml")
    return tmp_path


def read_manifest(repo):
    with (repo / "data" / "manifest.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_hash_of_a_known_value(repo):
    f = repo / "data" / "x.txt"
    f.write_text("abc", encoding="utf-8")
    # SHA-256("abc"), public reference value
    expected = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert manifest.register(f, "test") == expected
    assert read_manifest(repo)[0]["sha256"] == expected


def test_same_file_registered_twice_gives_one_row(repo):
    f = repo / "data" / "x.txt"
    f.write_text("abc", encoding="utf-8")
    manifest.register(f, "test")
    manifest.register(f, "test")
    assert len(read_manifest(repo)) == 1


def test_changed_content_adds_a_row_and_keeps_the_old_one(repo):
    f = repo / "data" / "x.txt"
    f.write_text("abc", encoding="utf-8")
    first = manifest.register(f, "test")
    f.write_text("abcd", encoding="utf-8")
    second = manifest.register(f, "test")
    rows = read_manifest(repo)
    assert len(rows) == 2
    assert [row["sha256"] for row in rows] == [first, second]


def test_manifest_with_only_its_header_does_not_get_a_second_header(repo):
    """`read_rows()` returns [] for a file without data rows: the header could be written twice."""
    m = repo / "data" / "manifest.csv"
    m.write_text(",".join(manifest.FIELDS) + "\n", encoding="utf-8")
    f = repo / "data" / "x.txt"
    f.write_text("abc", encoding="utf-8")
    manifest.register(f, "test")
    assert m.read_text(encoding="utf-8").count("sha256") == 1
    assert len(read_manifest(repo)) == 1


def test_verify_reports_nothing_when_everything_matches(repo):
    f = repo / "data" / "x.txt"
    f.write_text("abc", encoding="utf-8")
    manifest.register(f, "test")
    assert manifest.verify() == []


def test_verify_reports_a_missing_file(repo):
    f = repo / "data" / "x.txt"
    f.write_text("abc", encoding="utf-8")
    manifest.register(f, "test")
    f.unlink()
    assert [p for p in manifest.verify() if "missing" in p] == ["data/x.txt : missing"]


def test_verify_reports_a_different_hash(repo):
    f = repo / "data" / "x.txt"
    f.write_text("abc", encoding="utf-8")
    manifest.register(f, "test")
    f.write_text("other content", encoding="utf-8")
    assert len(manifest.verify()) == 1
    assert "hash" in manifest.verify()[0]


def test_verify_only_uses_the_most_recent_row(repo):
    """A path registered again after a change has several rows: the old one no longer counts."""
    f = repo / "data" / "x.txt"
    f.write_text("abc", encoding="utf-8")
    manifest.register(f, "test")
    f.write_text("abcd", encoding="utf-8")
    manifest.register(f, "test")
    assert len(read_manifest(repo)) == 2
    assert manifest.verify() == []
