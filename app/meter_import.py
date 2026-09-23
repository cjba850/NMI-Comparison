from __future__ import annotations

import csv
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


def parse_meter_csv(path: str | Path) -> list[MeterInterval]:
    """Parse the user's grid-import-only meter export.

    Expected fields:
      Role, Interval Date/Time, Part Description, Read Quality,
      Active UOM, Active Amt, Reactive UOM, Reactive Amt,
      Apparent UOM, Apparent Amt, Power Factor

    Amt is deliberately not used as consumption; Active Amt is authoritative.
    """
    path = Path(path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV has no header row")

        fieldnames = _clean_headers(reader.fieldnames)
        rows = csv.DictReader(f) if False else None

    # Re-open so we can provide cleaned fieldnames to DictReader.
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
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
                raise ValueError(
                    f"Invalid Interval Date/Time on line {line_no}: {ts_text!r}"
                ) from exc

            active = _to_kwh(_num(row.get("Active Amt")), row.get("Active UOM"))
            reactive = _num(row.get("Reactive Amt"))
            apparent = _num(row.get("Apparent Amt"))
            pf = _num(row.get("Power Factor"))

            intervals.append(MeterInterval(
                timestamp=ts,
                active_kwh=active,
                role=row.get("Role", "").strip(),
                part_description=row.get("Part Description", "").strip(),
                read_quality=row.get("Read Quality", "").strip(),
                reactive_kvarh=reactive,
                apparent_kvah=apparent,
                power_factor=pf,
            ))

    intervals.sort(key=lambda x: x.timestamp)
    return intervals


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
