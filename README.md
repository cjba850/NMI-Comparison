# NMI Energy Plan Calculator v0.11

A standalone FastAPI web service for replaying actual NMI electricity consumption against locally maintained electricity plans.

## What it does

Upload an NMI CSV and the application calculates usage statistics and historical plan costs using the actual interval consumption in the file.

For the supplied meter-export format, `Active Amt` is authoritative grid-import consumption. The parser supports the supplied Australian date format (`d/m/YYYY H:MM`) and KWH/MWH values.

The dashboard provides:

- total kWh
- average, minimum, maximum, median and P90 daily usage
- daily and monthly usage views
- interval/data-quality checks
- flat tariff replay
- time-of-use tariff replay
- wholesale/spot replay using supplied AEMO spot prices
- monthly cost breakdowns
- effective cost per kWh
- an explainable historical-cost comparison

## Local electricity plan management

Version 0.6 adds a **Manage plans** interface. You can create, edit and delete plans directly from the browser.

Plans are stored locally in:

```text
data/plans.json
```

Before a write, the previous file is retained as:

```text
data/plans.json.backup
```

No plan data is sent to a cloud database.

Supported plan types:

1. **Flat** — one usage rate plus daily supply charge.
2. **TOU** — any number of named periods with weekday/month selection, start/end times and rates.
3. **Wholesale / spot** — AEMO RRP plus a fixed retailer margin and other per-kWh component.

Historical tariff versions are supported using `effective_from` and `effective_to`. This is important when comparing five months of 2025 usage against the actual tariff that applied during those dates rather than today's tariff.

See `docs/PLAN_MANAGEMENT.md` and `docs/PLAN_SCHEMA.md` for details.

## Running

```bash
cd nmi-energy-calculator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Open:

```text
http://server-address:8080/
```

## Analysis year

Leave **Analysis year** blank to automatically detect the year when the CSV contains one year. If a CSV contains multiple years, select the required year explicitly.

## Important cost assumptions

The calculator is a historical replay tool. It does not predict future bills.

Supply charges are currently calculated for the calendar days represented in the uploaded data. For a partial year, treat the resulting total as the cost for the supplied period, not a full-year bill.

For wholesale plans, 30-minute NMI intervals are matched to the average of the six corresponding five-minute AEMO RRP values. The AEMO importer accepts common `REGION,SETTLEMENTDATE,TOTALDEMAND,RRP,PERIODTYPE` exports, including Australian `d/m/YYYY H:MM` timestamps. For `SETTLEMENTDATE` exports, the settlement timestamp is treated as the end of the five-minute interval and converted to the interval start before matching to NMI usage. This is an explicit approximation because the meter consumption is supplied at 30-minute resolution.

Actual retailer bills can contain additional charges, discounts, taxes, controlled-load components, demand charges, green-power products and other terms. The plan model now supports optional monthly peak-demand charges, but other bill-specific components still need to be configured before treating the result as a bill reproduction.

## Demand charges

A plan can optionally include a monthly peak-demand charge for any plan type (Flat, TOU or Wholesale). Configure one or more demand windows using weekdays, optional months and start/end times.

For each calendar month, the calculator finds the highest complete 30-minute import block inside the configured demand window(s), converts the block to average kW (`30-minute kWh × 2`), and calculates:

```text
monthly demand charge = peak kW × demand rate ($/kW/day) × calendar days in month
```

This follows the common demand-tariff structure documented by Momentum Energy, where the highest half-hour during the demand window sets the month's demand charge and the result is multiplied by the number of days in the month.

The demand detail in the calculation result shows the month, peak date/time, 30-minute kWh, calculated kW, applicable demand window and charge. Seasonal demand windows are supported, so a plan can have different demand periods for summer and winter.

## Tests

```bash
pytest -q
```

## Project layout

```text
app/
  main.py
  engine.py
  meter_import.py
  analysis.py
  reporting.py
  plan_store.py
  aemo_config.py

data/
  plans.json

docs/
  PLAN_SCHEMA.md
  PLAN_MANAGEMENT.md
  REPORTING.md
  DESIGN.md
  SYSTEMD.md
  COMMIT_MESSAGE.txt

static/
  index.html

tests/
```

## Security note

The plan-management API is intentionally simple and local. If the service is exposed through a reverse proxy, VPN or tunnel to untrusted users, add authentication/authorisation before allowing plan modifications.


### Plan cost components

Plan management now supports: 
- daily supply charge as a fixed dollar amount per day (`daily_supply_dollars`)
- optional monthly subscription/access fee (`monthly_subscription_dollars`), useful for wholesale products
- optional CL1 and CL2 controlled-load rates

The supplied meter format exposes total active import via `Active Amt` and does not split CL1/CL2 kWh. Therefore configured CL1/CL2 rates are retained for plan reference but are not included in calculated totals unless future meter data provides separate controlled-load registers.

### Demand surcharge

Plans can optionally include a demand surcharge, independent of whether the plan is Flat, TOU or Wholesale. When enabled, the calculator finds the highest complete 30-minute block on each local calendar day, converts block kWh to average kW (`kWh × 2`), and charges that demand at a configured `$ / kW` rate. 5-minute and 15-minute source data are aggregated into 30-minute blocks. Incomplete 30-minute blocks are excluded so missing meter data cannot artificially reduce the daily peak.

Demand is reported separately from energy, supply and subscription charges, including the daily peak block and calculated kW.
