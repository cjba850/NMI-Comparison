from __future__ import annotations
import json
import re
from pathlib import Path
from datetime import date

PLAN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,79}$")
ALLOWED_TYPES = {"flat", "tou", "wholesale"}

class PlanStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    def list(self) -> list[dict]:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("plans.json must contain a JSON array")
        return data

    def get(self, plan_id: str) -> dict | None:
        return next((p for p in self.list() if p.get("id") == plan_id), None)

    def save(self, plan: dict) -> dict:
        validate_plan(plan)
        plans = self.list()
        idx = next((i for i, p in enumerate(plans) if p.get("id") == plan["id"]), None)
        if idx is None:
            plans.append(plan)
        else:
            plans[idx] = plan
        self._write(plans)
        return plan

    def delete(self, plan_id: str) -> bool:
        plans = self.list()
        new = [p for p in plans if p.get("id") != plan_id]
        if len(new) == len(plans):
            return False
        self._write(new)
        return True

    def _write(self, plans: list[dict]):
        payload = json.dumps(plans, indent=2, ensure_ascii=False) + "\n"
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        backup = self.path.with_suffix(self.path.suffix + ".backup")
        if self.path.exists():
            backup.write_text(self.path.read_text(encoding="utf-8"), encoding="utf-8")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(self.path)

def validate_plan(plan: dict) -> None:
    if not isinstance(plan, dict):
        raise ValueError("Plan must be an object")
    for field in ("id", "provider", "name", "effective_from", "usage"):
        if field not in plan:
            raise ValueError(f"Missing required field: {field}")
    if not PLAN_ID_RE.fullmatch(str(plan["id"])):
        raise ValueError("Plan ID must be 2-80 characters using lowercase letters, numbers, dot, underscore or hyphen")
    if not str(plan["provider"]).strip() or not str(plan["name"]).strip():
        raise ValueError("Provider and plan name are required")
    start = date.fromisoformat(str(plan["effective_from"]))
    end_raw = plan.get("effective_to")
    if end_raw:
        end = date.fromisoformat(str(end_raw))
        if end < start:
            raise ValueError("effective_to cannot be before effective_from")
    daily = float(plan.get("daily_supply_dollars", plan.get("daily_supply_cents", 0) / 100.0))
    if daily < 0:
        raise ValueError("Daily supply charge cannot be negative")
    subscription = float(plan.get("monthly_subscription_dollars", 0))
    if subscription < 0:
        raise ValueError("Monthly subscription charge cannot be negative")
    demand = plan.get("demand", {})
    if demand is not None:
        if not isinstance(demand, dict):
            raise ValueError("demand must be an object")
        if "enabled" in demand and not isinstance(demand.get("enabled"), bool):
            raise ValueError("demand.enabled must be true or false")
        demand_rate = float(demand.get("rate_dollars_per_kw_per_day", demand.get("rate_dollars_per_kw", 0)))
        if demand_rate < 0:
            raise ValueError("Demand rate cannot be negative")
        windows = demand.get("windows", [])
        if demand.get("enabled", False):
            if not isinstance(windows, list):
                raise ValueError("demand.windows must be a list")
            for w in windows:
                if not isinstance(w, dict) or not w.get("name") or not w.get("start") or not w.get("end"):
                    raise ValueError("Each demand window requires name, start and end")
                days = w.get("days", list(range(7)))
                if any(int(d) not in range(7) for d in days):
                    raise ValueError("Demand window days must use 0=Monday through 6=Sunday")
                months = w.get("months")
                if months is not None and (not isinstance(months, list) or any(int(m) not in range(1, 13) for m in months)):
                    raise ValueError("Demand window months must use 1=January through 12=December")
    cl = plan.get("controlled_load", {})
    if cl is not None:
        if not isinstance(cl, dict):
            raise ValueError("controlled_load must be an object")
        for key in ("cl1_cents_per_kwh", "cl2_cents_per_kwh"):
            if cl.get(key) is not None and float(cl.get(key)) < 0:
                raise ValueError(f"{key} cannot be negative")
    usage = plan["usage"]
    if not isinstance(usage, dict) or usage.get("type") not in ALLOWED_TYPES:
        raise ValueError("usage.type must be flat, tou, or wholesale")
    typ = usage["type"]
    if typ == "flat":
        if float(usage.get("cents_per_kwh", -1)) < 0:
            raise ValueError("Flat cents_per_kwh must be zero or greater")
    elif typ == "tou":
        periods = usage.get("periods")
        if not isinstance(periods, list) or not periods:
            raise ValueError("TOU plans require at least one period")
        for p in periods:
            if not p.get("name") or not p.get("start") or not p.get("end"):
                raise ValueError("Each TOU period requires name, start and end")
            rate = float(p.get("cents_per_kwh", -1))
            if rate < 0:
                raise ValueError("TOU cents_per_kwh must be zero or greater")
            days = p.get("days", list(range(7)))
            if any(int(d) not in range(7) for d in days):
                raise ValueError("TOU days must use 0=Monday through 6=Sunday")
            months = p.get("months")
            if months is not None:
                if not isinstance(months, list) or any(int(m) not in range(1, 13) for m in months):
                    raise ValueError("TOU months must use 1=January through 12=December")
    else:
        for key in ("margin_cents_per_kwh", "other_cents_per_kwh"):
            if float(usage.get(key, 0)) < 0:
                raise ValueError(f"{key} cannot be negative")
