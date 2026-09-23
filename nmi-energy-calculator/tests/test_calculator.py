from datetime import datetime
from zoneinfo import ZoneInfo
from app.engine import parse_flat_csv, parse_nem12

SYDNEY = ZoneInfo("Australia/Sydney")


def test_flat_csv():
    csv_text='timestamp,kwh\n2026-01-01T00:00:00+11:00,1\n2026-01-01T00:30:00+11:00,2\n'
    intervals=parse_flat_csv(csv_text)
    assert len(intervals)==2
    assert sum(x.kwh for x in intervals)==3


def test_nem12_30min():
    values=",".join(["1"]*48)
    csv_text=("100,NEM12,202609231200,MDP,RET\n"
              "200,4102000000,E1,B1,1,E1,12345678,kWh,30,20260924\n"
              f"300,20260101,{values},A,,,20260101120000\n"
              "900,1\n")
    intervals=parse_nem12(csv_text)
    assert len(intervals)==48
    assert sum(x.kwh for x in intervals)==48
