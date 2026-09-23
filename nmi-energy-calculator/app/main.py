from __future__ import annotations
import json
from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from .engine import build_report, parse_aemo_spot_csv, parse_nmi_upload, calculate_plan

BASE_DIR = Path(__file__).resolve().parent.parent
PLANS_FILE = BASE_DIR / "data" / "plans.json"
app = FastAPI(title="NMI Energy Plan Calculator", version="0.2.0")


def load_plans():
    return json.loads(PLANS_FILE.read_text(encoding="utf-8"))


@app.get("/", response_class=HTMLResponse)
def index():
    return (BASE_DIR / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/plans")
def plans():
    return [{"id": p["id"], "provider": p["provider"], "name": p["name"], "type": p["usage"]["type"], "effective_from": p["effective_from"], "effective_to": p.get("effective_to")} for p in load_plans()]


@app.post("/api/calculate")
async def api_calculate(
    file: UploadFile = File(...),
    year: int = Form(...),
    region: str = Form("NSW1"),
    spot_file: UploadFile | None = File(None),
):
    raw = await file.read()
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(413, "NMI CSV exceeds 25 MB limit")
    try:
        intervals = parse_nmi_upload(raw.decode("utf-8-sig"))
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
        return build_report(results, year, file.filename or "upload.csv", region)
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
