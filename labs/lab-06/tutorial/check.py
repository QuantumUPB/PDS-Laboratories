"""Check the supplied report and, optionally, the student extension."""

import argparse
import csv
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--extension", action="store_true")
    args = parser.parse_args()
    root = Path("output")
    expected = {
        "S1": ("Central", 3, "11.33"),
        "S2": ("Riverside", 3, "15.33"),
        "S3": ("North Park", 2, "12.50"),
    }
    rows = list(csv.reader((root / "station-summary").open(newline="")))
    actual = {}
    for row in rows:
        if len(row) != 4:
            raise AssertionError(f"expected four columns, got {row!r}")
        station_id, name, count, average = row
        if station_id in actual:
            raise AssertionError(f"duplicate station {station_id}")
        actual[station_id] = (name, int(count), average)
    assert actual == expected, f"station report: {actual!r}"

    rejected = (root / "rejected").read_text().splitlines()
    assert len(rejected) == 2, f"expected two rejected records, got {len(rejected)}"
    assert any("t09" in row for row in rejected)
    assert any("t10" in row for row in rejected)
    print("PASS: station report and rejected records")

    if args.extension:
        rows = list(csv.reader((root / "long-trips").open(newline="")))
        actual = {station: int(count) for station, count in rows}
        assert len(rows) == 3, f"expected three stations, got {len(rows)} rows"
        assert actual == {"S1": 1, "S2": 2, "S3": 1}, actual
        print("PASS: long-trip counts")


if __name__ == "__main__":
    main()
