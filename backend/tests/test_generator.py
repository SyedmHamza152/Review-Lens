"""Synthetic dataset generator tests."""
import csv

from app.bigdata.generator import HEADER, generate_dataset


def test_generator_rowcount_and_schema(tmp_path):
    out = tmp_path / "gen.csv"
    generate_dataset(5000, out, seed=1)
    with out.open() as f:
        rows = list(csv.reader(f))
    assert rows[0] == HEADER
    assert len(rows) == 5001  # header + 5000


def test_generator_only_youtube_formats(tmp_path):
    out = tmp_path / "gen2.csv"
    generate_dataset(3000, out, seed=2)
    allowed = {"in_stream", "shorts", "in_feed"}
    with out.open() as f:
        reader = csv.DictReader(f)
        formats, platforms = set(), set()
        for row in reader:
            formats.add(row["ad_format"])
            platforms.add(row["platform"])
    assert formats <= allowed, f"forbidden formats leaked: {formats - allowed}"
    assert platforms == {"YouTube"}


def test_generator_deterministic(tmp_path):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    generate_dataset(500, a, seed=9)
    generate_dataset(500, b, seed=9)
    assert a.read_bytes() == b.read_bytes()


def test_generator_field_sanity(tmp_path):
    out = tmp_path / "g.csv"
    generate_dataset(1000, out, seed=3)
    with out.open() as f:
        for row in csv.DictReader(f):
            assert int(row["impressions"]) > 0
            assert int(row["clicks"]) >= 0
            assert float(row["spend"]) >= 0
            assert float(row["conversions"]) >= 0
