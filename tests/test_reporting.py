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
