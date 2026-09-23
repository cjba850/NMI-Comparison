# NMI Energy Plan Calculator

Standalone FastAPI web service for replaying actual electricity-meter interval data against configurable electricity plans.

## v0.5 — reporting dashboard

Version 0.5 adds a reporting layer on top of the v0.4 meter importer and tariff engines.

### What it does

- Uploads the supplied NMI CSV format and uses **Active Amt** + **Active UOM** as grid-import consumption.
- Supports flat, time-of-use (TOU), and wholesale/spot plan calculations.
- Accepts optional AEMO spot-price CSV data for wholesale plans.
- Calculates:
  - total consumption
  - average daily consumption
  - maximum and minimum usage day
  - median and P90 daily usage
  - monthly usage
  - hourly usage profile
  - plan energy cost, supply cost and total historical cost
  - effective total cost per kWh
- Shows a visual dashboard with daily/monthly usage and plan-cost charts.
- Provides an explainable **historical-cost recommendation**: the configured plan that produced the lowest calculated cost for the uploaded usage history.
- Provides a data-quality summary including interval length, gaps, duplicates, actual/estimated read counts and coverage.

### Important interpretation

The recommendation is a **historical replay**, not a forecast. It answers:

> "If this exact usage history had been charged under each configured plan, what would the calculated cost have been?"

It does not guarantee that the same plan will be cheapest in future. This is particularly important for wholesale plans because future spot prices can vary substantially.

## Project layout

```text
nmi-energy-calculator/
├── app/
│   ├── analysis.py       # Daily/monthly/profile/data-quality analysis
│   ├── aemo_config.py    # Optional AEMO API feature flag
│   ├── engine.py         # NMI/AEMO parsing and tariff engines
│   ├── main.py           # FastAPI application and reporting API
│   ├── meter_import.py   # Supplied NMI CSV parser/validation
│   └── reporting.py      # Plan comparison and recommendation
├── data/
│   └── plans.json        # Example plan definitions
├── docs/
│   ├── AEMO_API.md
│   ├── COMMIT_MESSAGE.txt
│   ├── DESIGN.md
│   ├── METER_CSV_FORMAT.md
│   ├── PLAN_SCHEMA.md
│   └── SYSTEMD.md
├── static/
│   └── index.html        # Standalone dashboard
├── tests/
└── requirements.txt
```

## Quick start

```bash
cd nmi-energy-calculator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`.

For a LAN-facing service, bind to an appropriate interface or put it behind a reverse proxy. See `docs/SYSTEMD.md` for a systemd example.

## NMI CSV format

The supported meter export contains columns such as:

```text
Role
Interval Date/Time
Part Description
Read Quality
UOM
Amt
Active UOM
Active Amt
Reactive UOM
Reactive Amt
Apparent UOM
Apparent Amt
Power Factor
```

For the grid-import-only use case, **Active Amt is authoritative**. `Amt` is deliberately ignored.

Australian timestamps such as `1/05/2025 0:00` are parsed as local `Australia/Sydney` time for tariff/reporting purposes.

`KWH` and `MWH` are supported. Reactive, apparent and power-factor fields are retained for validation/reporting but are not included in the energy charge calculation.

See `docs/METER_CSV_FORMAT.md`.

## Plan configuration

Plans are configured in `data/plans.json`. The included plans are deliberately fictional examples and must be replaced with real retailer plan data before using the results for a purchasing decision.

Supported usage types:

- `flat`
- `tou`
- `wholesale`

Daily supply charges are configured separately and are calculated for the calendar days represented by the uploaded data.

See `docs/PLAN_SCHEMA.md`.

## Wholesale calculation

Wholesale plans use AEMO RRP values in $/MWh. The engine converts these to cents/kWh and adds the configured retailer margin and other per-kWh component.

For 30-minute NMI data, the current implementation uses the average of the six matching five-minute spot prices. This is an explicit modelling assumption for interval replay; it is not a claim that a retailer's actual wholesale bill will be identical to spot price multiplied by consumption.

Wholesale results also report intervals for which a matching spot price was unavailable.

## AEMO API

The AEMO API integration remains optional and disabled by default. CSV uploads remain the standard path and do not require AEMO credentials or certificates.

See `docs/AEMO_API.md`.

## API

### `GET /api/plans`

Returns configured plan metadata.

### `POST /api/calculate`

Multipart form fields:

- `file` — NMI CSV
- `year` — reporting year
- `region` — NEM region, default `NSW1`
- `spot_file` — optional AEMO spot-price CSV

The response contains the plan calculations plus:

- `usage`
- `monthly_usage`
- `hourly_profile`
- `data_quality`
- `comparison.sorted_by_total_cost`
- `recommendation`
- `monthly_costs`

## Testing

From the project directory:

```bash
pytest -q
```

The tests cover the supplied meter format, validation, tariff calculations and AEMO configuration/parser behaviour.

## Production notes

- Replace the fictional plans before using the calculator for real plan selection.
- Record the source document and effective dates for each real plan.
- Keep historical plan definitions rather than overwriting old rates, so historical replays remain reproducible.
- Treat wholesale calculations as estimates unless the retailer's complete pricing structure is modelled.
- If the uploaded period is incomplete, use the coverage information before interpreting annual costs.
- For an external-facing deployment, add authentication, HTTPS and appropriate upload limits.
