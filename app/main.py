from __future__ import annotations
import json
from pathlib import Path
from datetime import timezone
from zoneinfo import ZoneInfo
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from .engine import build_report, parse_aemo_spot_csv, parse_nmi_upload, calculate_plan, Interval
from .meter_import import parse_meter_csv_text
from .analysis import usage_report, monthly_usage, hourly_profile, data_quality
from .reporting import plan_comparison, recommendation, _plan_monthly_costs
from .plan_store import PlanStore, validate_plan

BASE_DIR = Path(__file__).resolve().parent.parent
PLANS_FILE = BASE_DIR / "data" / "plans.json"
SYDNEY = ZoneInfo("Australia/Sydney")
app = FastAPI(title="NMI Energy Plan Calculator", version="0.6.0")
PLAN_STORE = PlanStore(PLANS_FILE)


def load_plans():
    return PLAN_STORE.list()


def parse_intervals(raw_text: str):
    # The supplied meter export has Active Amt/Active UOM and richer validation
    # metadata. Convert its local Australian timestamps to timezone-aware Intervals.
    if "Active Amt" in raw_text and "Interval Date/Time" in raw_text:
        rows = parse_meter_csv_text(raw_text)
        return [Interval(r.timestamp.replace(tzinfo=SYDNEY), r.active_kwh, "import", r.read_quality) for r in rows]
    return parse_nmi_upload(raw_text)


@app.get("/", response_class=HTMLResponse)
def index():
    return (BASE_DIR / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/plans")
def plans():
    return load_plans()


@app.post("/api/plans")
async def create_or_update_plan(plan: dict):
    try:
        validate_plan(plan)
        return PLAN_STORE.save(plan)
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.delete("/api/plans/{plan_id}")
def delete_plan(plan_id: str):
    if not PLAN_STORE.delete(plan_id):
        raise HTTPException(404, "Plan not found")
    return {"deleted": plan_id}


@app.get("/api/plans/{plan_id}")
def get_plan(plan_id: str):
    plan = PLAN_STORE.get(plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found")
    return plan


@app.post("/api/calculate")
async def api_calculate(
    file: UploadFile = File(...),
    year: int | None = Form(None),
    region: str = Form("NSW1"),
    spot_file: UploadFile | None = File(None),
):
    raw = await file.read()
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(413, "NMI CSV exceeds 25 MB limit")
    try:
        text = raw.decode("utf-8-sig")
        intervals = parse_intervals(text)
        if year is None:
            years = sorted({i.timestamp.astimezone(SYDNEY).year for i in intervals})
            if not years:
                raise ValueError("No dated interval data was found")
            if len(years) > 1:
                raise ValueError(f"CSV contains multiple years ({', '.join(map(str, years))}); select an analysis year")
            year = years[0]
        spot_prices = None
        if spot_file is not None:
            spot_raw = await spot_file.read()
            if len(spot_raw) > 100 * 1024 * 1024:
                raise HTTPException(413, "AEMO spot CSV exceeds 100 MB limit")
            spot_prices = parse_aemo_spot_csv(spot_raw.decode("utf-8-sig"), default_region=region)
        results = []
        for plan in load_plans():
            try:
                results.append(calculate_plan(intervals, plan, year, spot_prices, region))
            except ValueError as exc:
                results.append({"provider": plan["provider"], "plan": plan["name"], "plan_id": plan["id"], "type": plan["usage"]["type"], "error": str(exc)})

        report = build_report(results, year, file.filename or "upload.csv", region)
        report["usage"] = usage_report(intervals, year)
        report["monthly_usage"] = monthly_usage(intervals, year)
        report["hourly_profile"] = hourly_profile(intervals, year)
        report["data_quality"] = data_quality(intervals, year)
        report["comparison"] = {"sorted_by_total_cost": plan_comparison(results)}
        report["recommendation"] = recommendation(results)
        report["monthly_costs"] = {}
        for plan in load_plans():
            try:
                report["monthly_costs"][plan["id"]] = _plan_monthly_costs(intervals, plan, year, spot_prices, region)
            except ValueError:
                report["monthly_costs"][plan["id"]] = []
        return report
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
