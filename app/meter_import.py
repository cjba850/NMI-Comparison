from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class MeterInterval:
    timestamp: datetime
    active_kwh: float
    role: str = ""
    part_description: str = ""
    read_quality: str = ""
    reactive_kvarh: float | None = None
    apparent_kvah: float | None = None
    power_factor: float | None = None


def _clean_headers(headers):
    return [h.strip() if h is not None else "" for h in headers]


def _num(value):
    if value is None or str(value).strip() == "":
        return None
    return float(str(value).strip())


def _to_kwh(amount, uom):
    if amount is None:
        raise ValueError("Active Amt is required")
    unit = (uom or "").strip().upper()
    if unit == "KWH":
        return amount
    if unit == "MWH":
        return amount * 1000.0
    raise ValueError(f"Unsupported Active UOM: {uom!r}")


def parse_meter_csv_text(text: str) -> list[MeterInterval]:
    reader = csv.reader(io.StringIO(text))
    raw_headers = next(reader, None)
    if not raw_headers:
        raise ValueError("CSV has no header row")
    headers = _clean_headers(raw_headers)
    required = {"Interval Date/Time", "Active UOM", "Active Amt"}
    missing = required - set(headers)
    if missing:
        raise ValueError(f"Missing required column(s): {', '.join(sorted(missing))}")
    intervals = []
    for line_no, values in enumerate(reader, start=2):
        if not any(str(v).strip() for v in values):
            continue
        if len(values) < len(headers):
            values += [""] * (len(headers) - len(values))
        row = dict(zip(headers, values))
        ts_text = row["Interval Date/Time"].strip()
        try:
            ts = datetime.strptime(ts_text, "%d/%m/%Y %H:%M")
        except ValueError as exc:
            raise ValueError(f"Invalid Interval Date/Time on line {line_no}: {ts_text!r}") from exc
        active = _to_kwh(_num(row.get("Active Amt")), row.get("Active UOM"))
        intervals.append(MeterInterval(
            timestamp=ts, active_kwh=active, role=row.get("Role", "").strip(),
            part_description=row.get("Part Description", "").strip(), read_quality=row.get("Read Quality", "").strip(),
            reactive_kvarh=_num(row.get("Reactive Amt")), apparent_kvah=_num(row.get("Apparent Amt")),
            power_factor=_num(row.get("Power Factor")),
        ))
    intervals.sort(key=lambda x: x.timestamp)
    return intervals


def parse_meter_csv(path: str | Path) -> list[MeterInterval]:
    path = Path(path)
    return parse_meter_csv_text(path.read_text(encoding="utf-8-sig"))


def validate_intervals(intervals: list[MeterInterval]) -> dict:
    if not intervals:
        return {"count": 0, "duplicates": 0, "gaps": 0, "interval_minutes": None}

    timestamps = [i.timestamp for i in intervals]
    duplicates = len(timestamps) - len(set(timestamps))
    deltas = [
        int((b - a).total_seconds() / 60)
        for a, b in zip(timestamps, timestamps[1:])
        if b > a
    ]
    interval_minutes = max(set(deltas), key=deltas.count) if deltas else None
    gaps = sum(1 for d in deltas if interval_minutes and d > interval_minutes)
    return {
        "count": len(intervals),
        "duplicates": duplicates,
        "gaps": gaps,
        "interval_minutes": interval_minutes,
        "start": timestamps[0].isoformat(),
        "end": timestamps[-1].isoformat(),
        "total_kwh": round(sum(i.active_kwh for i in intervals), 6),
    }
