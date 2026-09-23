from pathlib import Path
from app.meter_import import parse_meter_csv, validate_intervals

SAMPLE = Path(__file__).resolve().parents[1] / "Sample.csv"

def test_sample_import():
    rows = parse_meter_csv(SAMPLE)
    assert len(rows) > 0
    assert rows[0].active_kwh == 0.173
    assert rows[0].read_quality == "Actual"
    assert rows[0].power_factor == 1.0

def test_validation():
    rows = parse_meter_csv(SAMPLE)
    report = validate_intervals(rows)
    assert report["count"] == len(rows)
    assert report["total_kwh"] > 0
