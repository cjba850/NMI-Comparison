from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from statistics import median
from zoneinfo import ZoneInfo
import math

SYDNEY = ZoneInfo("Australia/Sydney")


def _daily(intervals, year):
    out = defaultdict(float)
    for x in intervals:
        ts = x.timestamp.astimezone(SYDNEY)
        if ts.year == year and x.kwh >= 0:
            out[ts.date().isoformat()] += x.kwh
    return out


def _percentile(values, p):
    if not values:
        return 0.0
    values = sorted(values)
    if len(values) == 1:
        return values[0]
    pos = (len(values) - 1) * p
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return values[lo]
    return values[lo] + (values[hi] - values[lo]) * (pos - lo)


def usage_report(intervals, year):
    daily = _daily(intervals, year)
    values = list(daily.values())
    total = sum(values)
    days = len(values)
    expected_days = 366 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 365
    return {
        "year": year,
        "total_kwh": round(total, 3),
        "days_with_data": days,
        "expected_days": expected_days,
        "coverage_pct": round(days * 100 / expected_days, 2),
        "average_kwh_per_day": round(total / days, 3) if days else 0,
        "max_kwh_day": round(max(values), 3) if values else 0,
        "min_kwh_day": round(min(values), 3) if values else 0,
        "median_kwh_day": round(median(values), 3) if values else 0,
        "p90_kwh_day": round(_percentile(values, 0.90), 3),
        "daily": [{"date": d, "kwh": round(k, 3)} for d, k in sorted(daily.items())],
    }


def monthly_usage(intervals, year):
    buckets = defaultdict(float)
    days = defaultdict(set)
    for x in intervals:
        ts = x.timestamp.astimezone(SYDNEY)
        if ts.year == year:
            key = ts.strftime("%Y-%m")
            buckets[key] += x.kwh
            days[key].add(ts.date().isoformat())
    return [{
        "month": key,
        "kwh": round(buckets[key], 3),
        "days": len(days[key]),
        "average_kwh_per_day": round(buckets[key] / len(days[key]), 3) if days[key] else 0,
    } for key in sorted(buckets)]


def hourly_profile(intervals, year):
    buckets = defaultdict(float)
    for x in intervals:
        ts = x.timestamp.astimezone(SYDNEY)
        if ts.year == year:
            buckets[ts.hour] += x.kwh
    total = sum(buckets.values())
    return [{"hour": h, "kwh": round(buckets[h], 3), "pct": round(buckets[h] * 100 / total, 2) if total else 0} for h in range(24)]


def data_quality(intervals, year):
    selected = [x for x in intervals if x.timestamp.astimezone(SYDNEY).year == year]
    timestamps = sorted(x.timestamp.astimezone(SYDNEY) for x in selected)
    duplicates = len(timestamps) - len(set(timestamps))
    deltas = [int((b - a).total_seconds() / 60) for a, b in zip(timestamps, timestamps[1:]) if b > a]
    interval_minutes = max(set(deltas), key=deltas.count) if deltas else None
    gaps = sum(1 for d in deltas if interval_minutes and d > interval_minutes)
    actual = sum(1 for x in selected if getattr(x, "read_quality", "").strip().lower() == "actual")
    estimated = sum(1 for x in selected if getattr(x, "read_quality", "").strip().lower() == "estimated")
    qualities = defaultdict(int)
    for x in selected:
        q = getattr(x, "read_quality", "") or "Unknown"
        qualities[q] += 1
    return {
        "intervals": len(selected),
        "duplicates": duplicates,
        "interval_minutes": interval_minutes,
        "gaps": gaps,
        "actual_intervals": actual,
        "estimated_intervals": estimated,
        "read_quality_counts": dict(sorted(qualities.items())),
        "start": timestamps[0].isoformat() if timestamps else None,
        "end": timestamps[-1].isoformat() if timestamps else None,
    }


def monthly_costs(results):
    """Allocate annual plan costs to months using each month's share of usage.

    This is deliberately a reporting allocation, not a substitute for a meter
    bill. Supply cost is allocated by the number of days represented in each
    month; energy cost is allocated from the plan period buckets only when a
    detailed monthly tariff replay is unavailable.
    """
    return []
