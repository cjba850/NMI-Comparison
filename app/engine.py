from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import csv
import io
import json

SYDNEY = ZoneInfo("Australia/Sydney")


@dataclass(frozen=True)
class Interval:
    timestamp: datetime
    kwh: float
    register: str = "import"
    read_quality: str = ""


@dataclass(frozen=True)
class SpotPrice:
    timestamp: datetime
    region: str
    rrp_mwh: float


def local_interval(d: date, index: int, minutes: int) -> datetime:
    start = datetime.combine(d, time.min, tzinfo=SYDNEY).astimezone(timezone.utc)
    return (start + timedelta(minutes=index * minutes)).astimezone(SYDNEY)


def parse_nem12(text: str) -> list[Interval]:
    rows = list(csv.reader(io.StringIO(text)))
    out: list[Interval] = []
    interval_minutes = None
    register = "import"
    for row in rows:
        if not row:
            continue
        kind = row[0].strip()
        if kind == "200":
            if len(row) < 10:
                raise ValueError("Invalid NEM12 200 record")
            try:
                interval_minutes = int(row[8])
            except ValueError as exc:
                raise ValueError("Invalid NEM12 interval length") from exc
            # NEM12 register identifier is retained as metadata. The application
            # currently treats uploaded interval values as import consumption.
            register = row[2].strip() or "import"
        elif kind == "300":
            if interval_minutes is None:
                raise ValueError("NEM12 300 record appeared before a 200 record")
            d = datetime.strptime(row[1], "%Y%m%d").date()
            expected = 1440 // interval_minutes
            for i, raw in enumerate(row[2 : 2 + expected]):
                if raw == "":
                    continue
                try:
                    kwh = float(raw)
                except ValueError:
                    continue
                if kwh < 0:
                    continue
                out.append(Interval(local_interval(d, i, interval_minutes), kwh, register, ""))
    if not out:
        raise ValueError("No interval records were found in the NEM12 file")
    return out


def parse_flat_csv(text: str) -> list[Interval]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV has no header")
    fields = {f.strip().lower(): f.strip() for f in reader.fieldnames if f}

    if "timestamp" in fields and "kwh" in fields:
        out = []
        register_field = fields.get("register")
        for row in reader:
            if not row.get(fields["timestamp"]) or not row.get(fields["kwh"]):
                continue
            ts = datetime.fromisoformat(row[fields["timestamp"]].replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=SYDNEY)
            register = row.get(register_field, "import") if register_field else "import"
            out.append(Interval(ts.astimezone(SYDNEY), float(row[fields["kwh"]]), register or "import", ""))
        if out:
            return out

    settlement = fields.get("settlementdate")
    if settlement:
        periods = []
        for col in reader.fieldnames:
            low = col.strip().lower()
            if low.startswith("period "):
                try:
                    periods.append((int(low.split()[1]), col))
                except (IndexError, ValueError):
                    pass
        periods.sort()
        if periods:
            step = 1440 // len(periods)
            out = []
            for row in reader:
                if not row.get(settlement):
                    continue
                d = datetime.strptime(row[settlement], "%Y%m%d").date()
                for i, (_, col) in enumerate(periods):
                    raw = row.get(col)
                    if raw not in (None, ""):
                        out.append(Interval(local_interval(d, i, step), float(raw), "import", ""))
            if out:
                return out
    raise ValueError("Unsupported CSV format. Use NEM12, timestamp/kWh CSV, or AEMO CSVIntervalData format.")


def parse_nmi_upload(text: str) -> list[Interval]:
    if any(x.startswith("100,NEM12,") for x in text.splitlines()[:10]):
        return parse_nem12(text)
    return parse_flat_csv(text)


def _normalise_header(row: list[str]) -> dict[str, str]:
    return {str(x).strip().lower(): x.strip() for x in row if x}


def _parse_aemo_datetime(raw: str) -> datetime:
    raw = raw.strip()
    # AEMO exports commonly use Australian local time as d/m/YYYY H:MM,
    # while other APIs/reports use ISO-like formats.
    for fmt in (
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d %H:%M",
    ):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=SYDNEY)
        except ValueError:
            pass
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return (dt if dt.tzinfo else dt.replace(tzinfo=SYDNEY)).astimezone(SYDNEY)


def parse_aemo_spot_csv(text: str, default_region: str | None = None) -> list[SpotPrice]:
    """Parse common AEMO PRICESOLUTION/TRADINGPRICE-style CSVs or simple CSVs.

    Supports both ordinary header/data CSVs and AEMO payloads containing I/C/D
    records. AEMO report payloads commonly put a ``D`` record marker before the
    actual data fields, so the marker is removed before header lookup.
    """
    rows = list(csv.reader(io.StringIO(text)))
    header_names: list[str] | None = None
    out: list[SpotPrice] = []

    for row in rows:
        if not row:
            continue
        cells = [c.strip() for c in row]
        lowered = [c.lower() for c in cells]

        # Any row containing the useful field names can be treated as a header.
        if "rrp" in lowered and ("interval_datetime" in lowered or "settlementdate" in lowered):
            header_names = lowered
            continue

        if header_names is None:
            continue

        data = cells[1:] if cells and cells[0].lower() == "d" else cells
        if len(data) < len(header_names):
            continue
        if len(data) > len(header_names):
            data = data[:len(header_names)]
        record = dict(zip(header_names, data))

        # The SETTLEMENTDATE/RRP export supplied by the user is a 5-minute
        # trading-price table.  PERIODTYPE=TRADE is the relevant series;
        # ignore other period types when present.
        period_type = (record.get("periodtype") or "").strip().upper()
        if period_type and period_type not in {"TRADE", "TRADING"}:
            continue

        ts_raw = record.get("interval_datetime") or record.get("timestamp")
        region = record.get("regionid") or record.get("region") or default_region
        rrp_raw = record.get("rrp") or record.get("price")
        if not ts_raw:
            sd = record.get("settlementdate")
            period = record.get("periodid") or record.get("dispatchinterval")
            if sd and period:
                try:
                    # PERIODID in the five-minute trading-price context is a
                    # five-minute period number within the settlement date.
                    d = datetime.strptime(sd[:8], "%Y%m%d").replace(tzinfo=SYDNEY)
                    ts_raw = (d + timedelta(minutes=(int(period) - 1) * 5)).isoformat()
                except (ValueError, TypeError):
                    pass

        # In this export SETTLEMENTDATE is the end of the five-minute
        # settlement interval (e.g. 00:05 is the price for 00:00-00:05).
        # Internally the calculator uses interval start timestamps, so shift
        # these records back by five minutes.
        settlement_only = not (record.get("interval_datetime") or record.get("timestamp"))
        if not ts_raw or not rrp_raw or not region:
            continue
        try:
            ts = _parse_aemo_datetime(ts_raw)
            if settlement_only and record.get("settlementdate"):
                ts -= timedelta(minutes=5)
            out.append(SpotPrice(ts, str(region).strip().upper(), float(rrp_raw)))
        except (ValueError, TypeError):
            continue

    if not out:
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames:
            f = {x.strip().lower(): x for x in reader.fieldnames}
            for row in reader:
                ts_key = f.get("interval_datetime", f.get("timestamp", ""))
                ts = row.get(ts_key) if ts_key else row.get(f.get("settlementdate", ""))
                price = row.get(f.get("rrp", f.get("price", "")))
                region = row.get(f.get("regionid", f.get("region", ""))) or default_region
                period_type = (row.get(f.get("periodtype", ""), "") or "").strip().upper()
                if period_type and period_type not in {"TRADE", "TRADING"}:
                    continue
                if ts and price and region:
                    try:
                        parsed = _parse_aemo_datetime(ts)
                        if not ts_key and f.get("settlementdate"):
                            parsed -= timedelta(minutes=5)
                        out.append(SpotPrice(parsed, str(region).strip().upper(), float(price)))
                    except ValueError:
                        pass
    if not out:
        raise ValueError("No AEMO spot-price records were found. Expected INTERVAL_DATETIME/RRP or SETTLEMENTDATE/PERIODID/RRP.")
    return out


def applies(plan: dict, d: date) -> bool:
    start = date.fromisoformat(plan["effective_from"])
    end = date.fromisoformat(plan["effective_to"]) if plan.get("effective_to") else None
    return d >= start and (end is None or d <= end)


def tou_rate(usage: dict, ts: datetime) -> tuple[str, float]:
    weekday = ts.weekday()
    month = ts.month
    current = ts.timetz().replace(tzinfo=None)
    for p in usage.get("periods", []):
        months = p.get("months")
        if months is not None and month not in [int(m) for m in months]:
            continue
        if weekday not in p.get("days", list(range(7))):
            continue
        start = time.fromisoformat(p["start"])
        end = time.fromisoformat(p["end"])
        matches = (start <= current < end) if start <= end else (current >= start or current < end)
        if matches:
            return p["name"], float(p["cents_per_kwh"])
    raise ValueError(f"No TOU period matches {ts.isoformat()}")


def _daily_supply_cents(plan: dict) -> float:
    # v0.8 stores the supply charge as dollars/day. Keep the old cents/day
    # field readable for backwards compatibility with existing plan files.
    if "daily_supply_dollars" in plan:
        return float(plan.get("daily_supply_dollars", 0)) * 100.0
    return float(plan.get("daily_supply_cents", 0))

def _monthly_subscription_cents(plan: dict) -> float:
    return float(plan.get("monthly_subscription_dollars", 0)) * 100.0

def _controlled_load_config(plan: dict) -> dict:
    cfg = plan.get("controlled_load", {})
    return cfg if isinstance(cfg, dict) else {}

def _base_result(plan: dict, year: int, selected: list[Interval], energy_cents: float, buckets: dict, notes: list[str], supply_days: int, month_count: int = 0) -> dict:
    supply = supply_days * _daily_supply_cents(plan)
    subscription = month_count * _monthly_subscription_cents(plan)
    usage_kwh = sum(x.kwh for x in selected)
    return {
        "provider": plan["provider"], "plan": plan["name"], "plan_id": plan["id"], "type": plan["usage"]["type"], "year": year,
        "days_with_data": supply_days, "intervals": len(selected), "usage_kwh": round(usage_kwh, 3),
        "energy_cost": round(energy_cents / 100, 2), "supply_cost": round(supply / 100, 2),
        "subscription_cost": round(subscription / 100, 2),
        "total_cost": round((energy_cents + supply + subscription) / 100, 2),
        "periods": {n: {"kwh": round(v["kwh"], 3), "cost": round(v["cost_cents"] / 100, 2), "rate_cents_per_kwh": round(v["rate_cents_per_kwh"], 5)} for n, v in buckets.items()},
        "notes": notes,
    }


def calculate_flat_or_tou(intervals: list[Interval], plan: dict, year: int) -> dict:
    selected = [x for x in intervals if x.timestamp.astimezone(SYDNEY).year == year and x.register.lower() == "import"]
    selected = [x for x in selected if applies(plan, x.timestamp.astimezone(SYDNEY).date())]
    if not selected:
        raise ValueError(f"No import interval data covered by plan {plan['name']} for {year}")
    energy = 0.0
    buckets: dict = {}
    usage = plan["usage"]
    for item in selected:
        ts = item.timestamp.astimezone(SYDNEY)
        if usage["type"] == "flat":
            name, rate = "flat", float(usage["cents_per_kwh"])
        elif usage["type"] == "tou":
            name, rate = tou_rate(usage, ts)
        else:
            raise ValueError(f"Unsupported usage type: {usage['type']}")
        cost = item.kwh * rate
        energy += cost
        b = buckets.setdefault(name, {"kwh": 0.0, "cost_cents": 0.0, "rate_cents_per_kwh": rate})
        b["kwh"] += item.kwh
        b["cost_cents"] += cost
    days_set = {x.timestamp.astimezone(SYDNEY).date() for x in selected}
    days = len(days_set)
    months = len({d.strftime("%Y-%m") for d in days_set})
    notes = ["Supply charge uses calendar days represented in the uploaded data."]
    cl = _controlled_load_config(plan)
    if cl.get("cl1_cents_per_kwh") is not None or cl.get("cl2_cents_per_kwh") is not None:
        notes.append("Controlled-load rates are configured, but this calculation only applies them when the uploaded meter data identifies separate CL1/CL2 registers. The supplied import-only data does not split controlled-load kWh.")
    return _base_result(plan, year, selected, energy, buckets, notes, days, months)


def _spot_map(prices: list[SpotPrice], region: str) -> dict[datetime, float]:
    values = {}
    for p in prices:
        if p.region.upper() == region.upper():
            values[p.timestamp.astimezone(SYDNEY).replace(second=0, microsecond=0)] = p.rrp_mwh
    return values


def calculate_wholesale(intervals: list[Interval], plan: dict, year: int, prices: list[SpotPrice], region: str) -> dict:
    selected = [x for x in intervals if x.timestamp.astimezone(SYDNEY).year == year and x.register.lower() == "import"]
    selected = [x for x in selected if applies(plan, x.timestamp.astimezone(SYDNEY).date())]
    if not selected:
        raise ValueError(f"No import interval data covered by plan {plan['name']} for {year}")
    spot = _spot_map(prices, region)
    cfg = plan["usage"]
    margin = float(cfg.get("margin_cents_per_kwh", 0))
    other = float(cfg.get("other_cents_per_kwh", 0))
    energy = 0.0
    buckets: dict = {}
    missing = 0
    for item in selected:
        ts = item.timestamp.astimezone(SYDNEY)
        if not applies(plan, ts.date()):
            continue
        # NEM interval exports are commonly 30-minute. At a half-hour boundary
        # use all six five-minute prices. For a non-half-hour timestamp that is
        # five-minute aligned, use the matching spot interval.
        start = ts.replace(second=0, microsecond=0)
        if ts.minute % 30 == 0:
            samples = [spot.get(start + timedelta(minutes=5 * i)) for i in range(6)]
            samples = [x for x in samples if x is not None]
            if not samples:
                missing += 1
                continue
            effective_spot = (sum(samples) / len(samples)) / 10.0
            method = "30min_average_of_5min_prices"
        elif ts.minute % 5 == 0 and start in spot:
            effective_spot = spot[start] / 10.0  # $/MWh -> cents/kWh
            method = "5min"
        else:
            missing += 1
            continue
        rate = effective_spot + margin + other
        cost = item.kwh * rate
        energy += cost
        key = "spot" if method == "5min" else "spot_30min_average"
        b = buckets.setdefault(key, {"kwh": 0.0, "cost_cents": 0.0, "rate_cents_per_kwh": effective_spot})
        b["kwh"] += item.kwh
        b["cost_cents"] += cost
    if not energy and missing:
        raise ValueError(f"No matching AEMO spot prices for region {region} and {year}")
    days_set = {x.timestamp.astimezone(SYDNEY).date() for x in selected}
    days = len(days_set)
    months = len({d.strftime("%Y-%m") for d in days_set})
    notes = [
        f"Wholesale calculation uses AEMO RRP for region {region}.",
        f"Wholesale retailer add-ons: {margin:.4f} c/kWh margin + {other:.4f} c/kWh other component.",
    ]
    monthly_fee = float(plan.get("monthly_subscription_dollars", 0))
    if monthly_fee:
        notes.append(f"Wholesale subscription/access fee: ${monthly_fee:.2f} per month, applied for each month represented in the uploaded data.")
    if any(x.timestamp.astimezone(SYDNEY).minute % 5 for x in selected):
        notes.append("NMI intervals are not 5-minute aligned; matching uses the average of available five-minute prices across each 30-minute interval.")
    if missing:
        notes.append(f"{missing} NMI intervals had no matching spot price and were excluded from wholesale energy cost.")
    result = _base_result(plan, year, selected, energy, buckets, notes, days, months)
    result["wholesale"] = {"region": region, "spot_intervals": len(spot), "missing_intervals": missing, "margin_cents_per_kwh": margin, "other_cents_per_kwh": other, "monthly_subscription_dollars": float(plan.get("monthly_subscription_dollars", 0))}
    return result


def calculate_plan(intervals: list[Interval], plan: dict, year: int, spot_prices: list[SpotPrice] | None = None, region: str | None = None) -> dict:
    if plan["usage"]["type"] in {"flat", "tou"}:
        return calculate_flat_or_tou(intervals, plan, year)
    if plan["usage"]["type"] == "wholesale":
        if not spot_prices or not region:
            raise ValueError("Wholesale plan requires AEMO spot-price data and a NEM region")
        return calculate_wholesale(intervals, plan, year, spot_prices, region)
    raise ValueError(f"Unsupported usage type: {plan['usage']['type']}")


def build_report(results: list[dict], year: int, filename: str, region: str | None = None) -> dict:
    valid = [r for r in results if "error" not in r]
    if not valid:
        return {"year": year, "filename": filename, "region": region, "plans": results, "comparison": {}}
    baseline = valid[0]["total_cost"]
    comparison = []
    for r in sorted(valid, key=lambda x: x["total_cost"]):
        comparison.append({
            "plan_id": r["plan_id"], "provider": r["provider"], "plan": r["plan"], "type": r["type"],
            "total_cost": r["total_cost"], "difference_from_first": round(r["total_cost"] - valid[0]["total_cost"], 2),
            "difference_from_baseline": round(r["total_cost"] - baseline, 2), "usage_kwh": r["usage_kwh"],
            "effective_cents_per_kwh": round((r["total_cost"] * 100) / r["usage_kwh"], 4) if r["usage_kwh"] else None,
        })
    return {"year": year, "filename": filename, "region": region, "plans": results, "comparison": {"sorted_by_total_cost": comparison}}
