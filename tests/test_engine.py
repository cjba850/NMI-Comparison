from datetime import datetime
from zoneinfo import ZoneInfo
from app.engine import Interval, SpotPrice, calculate_plan, parse_aemo_spot_csv, parse_flat_csv

SYDNEY = ZoneInfo("Australia/Sydney")


def test_flat_plan():
    intervals = [Interval(datetime(2026, 1, 1, 0, 0, tzinfo=SYDNEY), 2), Interval(datetime(2026, 1, 2, 0, 0, tzinfo=SYDNEY), 3)]
    plan = {"id":"test","provider":"Test","name":"Flat","effective_from":"2026-01-01","effective_to":None,"daily_supply_cents":100,"usage":{"type":"flat","cents_per_kwh":20}}
    r = calculate_plan(intervals, plan, 2026)
    assert r["usage_kwh"] == 5
    assert r["total_cost"] == 3.0


def test_tou_peak_and_offpeak():
    intervals = [
        Interval(datetime(2026, 1, 5, 15, 0, tzinfo=SYDNEY), 2),
        Interval(datetime(2026, 1, 5, 21, 0, tzinfo=SYDNEY), 3),
    ]
    plan = {"id":"test","provider":"Test","name":"TOU","effective_from":"2026-01-01","effective_to":None,"daily_supply_cents":0,"usage":{"type":"tou","periods":[{"name":"peak","days":[0,1,2,3,4],"start":"14:00","end":"20:00","cents_per_kwh":40},{"name":"offpeak","days":[0,1,2,3,4,5,6],"start":"20:00","end":"14:00","cents_per_kwh":10}]}}
    r = calculate_plan(intervals, plan, 2026)
    assert r["periods"]["peak"]["kwh"] == 2
    assert r["periods"]["offpeak"]["kwh"] == 3
    assert r["total_cost"] == 1.1


def test_aemo_simple_spot_csv():
    text = "INTERVAL_DATETIME,REGIONID,RRP\n2026-01-01T00:00:00+11:00,NSW1,100\n"
    prices = parse_aemo_spot_csv(text)
    assert prices[0].region == "NSW1"
    assert prices[0].rrp_mwh == 100


def test_aemo_d_record_csv():
    text = "I,GPG,PRICESOLUTION,1\nINTERVAL_DATETIME,REGIONID,RRP\nD,2026-01-01T00:00:00+11:00,NSW1,100\n"
    prices = parse_aemo_spot_csv(text)
    assert len(prices) == 1
    assert prices[0].rrp_mwh == 100


def test_wholesale_30min_averages_six_prices():
    intervals = [Interval(datetime(2026, 1, 1, 0, 0, tzinfo=SYDNEY), 6)]
    prices = [SpotPrice(datetime(2026, 1, 1, 0, i * 5, tzinfo=SYDNEY), "NSW1", 100 + i * 10) for i in range(6)]
    plan = {"id":"test","provider":"Test","name":"Wholesale","effective_from":"2026-01-01","effective_to":None,"daily_supply_cents":0,"usage":{"type":"wholesale","margin_cents_per_kwh":5,"other_cents_per_kwh":0}}
    r = calculate_plan(intervals, plan, 2026, prices, "NSW1")
    # Mean RRP = 125 $/MWh = 12.5 c/kWh; + 5c margin = 17.5c/kWh; 6kWh => $1.05
    assert r["total_cost"] == 1.05
    assert r["wholesale"]["missing_intervals"] == 0


def test_aemo_settlementdate_trade_csv():
    text = """REGION,SETTLEMENTDATE,TOTALDEMAND,RRP,PERIODTYPE
NSW1,1/01/2026 0:05,6713.88,71.24,TRADE
NSW1,1/01/2026 0:10,6751.48,65.31,TRADE
NSW1,1/01/2026 0:15,6715.71,69.28,TRADE
"""
    prices = parse_aemo_spot_csv(text)
    assert len(prices) == 3
    assert prices[0].region == "NSW1"
    assert prices[0].timestamp == datetime(2026, 1, 1, 0, 0, tzinfo=SYDNEY)
    assert prices[0].rrp_mwh == 71.24
    assert prices[1].timestamp == datetime(2026, 1, 1, 0, 5, tzinfo=SYDNEY)


def test_aemo_settlementdate_ignores_non_trade_rows():
    text = """REGION,SETTLEMENTDATE,TOTALDEMAND,RRP,PERIODTYPE
NSW1,1/01/2026 0:05,6713.88,71.24,TRADE
NSW1,1/01/2026 0:05,6713.88,999.99,OTHER
"""
    prices = parse_aemo_spot_csv(text)
    assert len(prices) == 1
    assert prices[0].rrp_mwh == 71.24


def test_daily_supply_is_dollars_and_monthly_subscription_applies():
    from app.engine import calculate_plan, Interval
    from datetime import datetime
    plan = {"id":"test-fees","provider":"Test","name":"Fees","effective_from":"2026-01-01","effective_to":None,"daily_supply_dollars":1.10,"monthly_subscription_dollars":12.50,"usage":{"type":"flat","cents_per_kwh":20}}
    intervals = [Interval(datetime(2026,1,1,0,0),1.0), Interval(datetime(2026,2,1,0,0),1.0)]
    result = calculate_plan(intervals, plan, 2026)
    assert result["energy_cost"] == 0.4
    assert result["supply_cost"] == 2.2
    assert result["subscription_cost"] == 25.0
    assert result["total_cost"] == 27.6


def test_controlled_load_rates_are_reported_but_not_applied_without_separate_registers():
    from app.engine import calculate_plan, Interval
    from datetime import datetime
    plan = {"id":"test-cl","provider":"Test","name":"CL","effective_from":"2026-01-01","effective_to":None,"daily_supply_dollars":0,"controlled_load":{"cl1_cents_per_kwh":12,"cl2_cents_per_kwh":8},"usage":{"type":"flat","cents_per_kwh":20}}
    result = calculate_plan([Interval(datetime(2026,1,1,0,0),2.0)], plan, 2026)
    assert result["total_cost"] == 0.4
    assert any("Controlled-load rates are configured" in n for n in result["notes"])
