from datetime import datetime
from zoneinfo import ZoneInfo
from app.engine import Interval
from app.analysis import usage_report, monthly_usage, data_quality
from app.reporting import plan_comparison, recommendation

SYDNEY = ZoneInfo("Australia/Sydney")

def test_usage_report():
    rows = [Interval(datetime(2026,1,1,0,0,tzinfo=SYDNEY), 2, read_quality="Actual"), Interval(datetime(2026,1,1,0,30,tzinfo=SYDNEY), 3, read_quality="Actual")]
    r = usage_report(rows, 2026)
    assert r["total_kwh"] == 5
    assert r["max_kwh_day"] == 5
    assert r["days_with_data"] == 1

def test_monthly_and_quality():
    rows = [Interval(datetime(2026,1,1,0,0,tzinfo=SYDNEY), 1, read_quality="Actual"), Interval(datetime(2026,2,1,0,0,tzinfo=SYDNEY), 2, read_quality="Estimated")]
    m = monthly_usage(rows, 2026)
    assert [x["kwh"] for x in m] == [1, 2]
    q = data_quality(rows, 2026)
    assert q["actual_intervals"] == 1
    assert q["estimated_intervals"] == 1

def test_recommendation_and_comparison():
    results = [
        {"plan_id":"a","provider":"A","plan":"A","type":"flat","total_cost":100,"energy_cost":80,"supply_cost":20,"usage_kwh":1000},
        {"plan_id":"b","provider":"B","plan":"B","type":"tou","total_cost":110,"energy_cost":90,"supply_cost":20,"usage_kwh":1000},
    ]
    c = plan_comparison(results)
    assert c[0]["plan_id"] == "a"
    assert c[1]["difference_from_lowest"] == 10
    assert recommendation(results)["plan_id"] == "a"

def test_monthly_cost_report_includes_monthly_demand_charge():
    from app.reporting import _plan_monthly_costs
    rows = [
        Interval(datetime(2026,1,5,17,0,tzinfo=SYDNEY), 2.0),
        Interval(datetime(2026,1,5,17,30,tzinfo=SYDNEY), 5.0),
    ]
    plan = {
        "id":"demand-report", "provider":"Test", "name":"Demand", "effective_from":"2026-01-01", "effective_to":None,
        "daily_supply_dollars":0, "usage":{"type":"flat","cents_per_kwh":0},
        "demand":{"enabled":True,"rate_dollars_per_kw_per_day":0.25,"windows":[{"name":"Peak","days":[0,1,2,3,4],"start":"17:00","end":"18:00"}]},
    }
    result = _plan_monthly_costs(rows, plan, 2026)
    assert result[0]["demand_cost"] == 77.5
    assert result[0]["total_cost"] == 77.5
