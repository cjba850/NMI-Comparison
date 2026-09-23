from __future__ import annotations
from collections import defaultdict
from datetime import date


def _month_key(ts):
    return ts.strftime("%Y-%m")


def _plan_monthly_costs(intervals, plan, year, spot_prices=None, region=None):
    from .engine import calculate_plan
    from .engine import applies, tou_rate, _spot_map

    selected = [x for x in intervals if x.timestamp.year == year and x.register.lower() == "import"]
    months = defaultdict(lambda: {"kwh": 0.0, "energy_cost_cents": 0.0, "days": set()})
    spot = _spot_map(spot_prices or [], region or "") if plan["usage"]["type"] == "wholesale" else {}
    usage = plan["usage"]
    for item in selected:
        ts = item.timestamp
        if not applies(plan, ts.date()):
            continue
        key = _month_key(ts)
        m = months[key]
        m["kwh"] += item.kwh
        m["days"].add(ts.date())
        if usage["type"] == "flat":
            rate = float(usage["cents_per_kwh"])
        elif usage["type"] == "tou":
            _, rate = tou_rate(usage, ts)
        else:
            start = ts.replace(second=0, microsecond=0)
            if ts.minute % 30 == 0:
                samples = [spot.get(start.replace(second=0, microsecond=0) + __import__('datetime').timedelta(minutes=5*i)) for i in range(6)]
                samples = [v for v in samples if v is not None]
                if not samples:
                    continue
                rate = (sum(samples) / len(samples)) / 10.0 + float(usage.get("margin_cents_per_kwh", 0)) + float(usage.get("other_cents_per_kwh", 0))
            elif ts.minute % 5 == 0 and start in spot:
                rate = spot[start] / 10.0 + float(usage.get("margin_cents_per_kwh", 0)) + float(usage.get("other_cents_per_kwh", 0))
            else:
                continue
        m["energy_cost_cents"] += item.kwh * rate

    supply = float(plan.get("daily_supply_dollars", plan.get("daily_supply_cents", 0) / 100.0)) * 100
    out = []
    for key in sorted(months):
        m = months[key]
        subscription = float(plan.get("monthly_subscription_dollars", 0)) * 100
        out.append({"month": key, "kwh": round(m["kwh"], 3), "energy_cost": round(m["energy_cost_cents"] / 100, 2), "supply_cost": round(len(m["days"]) * supply / 100, 2), "subscription_cost": round(subscription / 100, 2), "total_cost": round((m["energy_cost_cents"] + len(m["days"]) * supply + subscription) / 100, 2)})
    return out


def plan_comparison(results):
    valid = [r for r in results if "error" not in r]
    if not valid:
        return []
    ordered = sorted(valid, key=lambda r: r["total_cost"])
    lowest = ordered[0]["total_cost"]
    return [{
        "plan_id": r["plan_id"], "provider": r["provider"], "plan": r["plan"], "type": r["type"],
        "total_cost": r["total_cost"], "energy_cost": r["energy_cost"], "supply_cost": r["supply_cost"],
        "usage_kwh": r["usage_kwh"], "effective_cents_per_kwh": round(r["total_cost"] * 100 / r["usage_kwh"], 4) if r["usage_kwh"] else None,
        "difference_from_lowest": round(r["total_cost"] - lowest, 2),
        "savings_vs_lowest": round(lowest - r["total_cost"], 2),
    } for r in ordered]


def recommendation(results):
    valid = [r for r in results if "error" not in r]
    if not valid:
        return {"available": False, "message": "No plans could be calculated."}
    ordered = sorted(valid, key=lambda r: r["total_cost"])
    first = ordered[0]
    if len(ordered) > 1:
        gap = ordered[1]["total_cost"] - first["total_cost"]
        pct = gap * 100 / first["total_cost"] if first["total_cost"] else 0
    else:
        gap, pct = 0, 0
    message = f"Based on the supplied usage history, {first['provider']} — {first['plan']} produced the lowest calculated historical cost."
    if len(ordered) > 1 and pct < 2:
        message += " The difference from the next-lowest calculated plan is small, so plan terms and future-price exposure should also be considered."
    return {"available": True, "plan_id": first["plan_id"], "provider": first["provider"], "plan": first["plan"], "historical_cost": first["total_cost"], "next_lowest_gap": round(gap, 2), "next_lowest_gap_pct": round(pct, 2), "message": message, "basis": "Historical replay of the uploaded consumption against the configured plan definitions; this is not a forecast of future bills."}
