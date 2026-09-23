# Local plan management

Version 0.11 includes a browser interface for maintaining the electricity plans used by the calculator.

## Where plans are stored

Plans are stored in:

```text
data/plans.json
```

The application also creates:

```text
data/plans.json.backup
```

before replacing the current plan file. The JSON file is deliberately human-readable and can be version-controlled with the project.

## Adding a plan

Open the **Manage plans** tab and select **Add plan**.

The editor supports:

- Provider
- Plan name and unique local plan ID
- Effective-from and effective-to dates
- Daily supply charge
- Flat usage rate
- Multiple TOU periods with optional month restrictions
- Wholesale/spot margin and other per-kWh components
- Source URL
- Source/document notes
- Last verified date

For TOU plans, days use Python weekday numbering:

- 0 Monday
- 1 Tuesday
- 2 Wednesday
- 3 Thursday
- 4 Friday
- 5 Saturday
- 6 Sunday

A period can cross midnight, for example `22:00` to `07:00`.

## Historical plans

Use the effective dates to keep historical tariff versions separate. For example:

```text
acme-flat-2025    2025-01-01 → 2025-06-30
acme-flat-2025b   2025-07-01 → 2025-12-31
acme-flat-2026    2026-01-01 → current
```

The calculator only applies a plan version to meter intervals whose dates fall inside that effective period.

## Wholesale plans

Wholesale plans do not contain the AEMO spot price in `plans.json`. They contain the retailer's fixed additions, such as:

```json
"usage": {
  "type": "wholesale",
  "margin_cents_per_kwh": 8.0,
  "other_cents_per_kwh": 0.0
}
```

The AEMO RRP is supplied separately when running a calculation.

## API

The web interface uses these local endpoints:

- `GET /api/plans` — list all plans
- `GET /api/plans/{id}` — retrieve one plan
- `POST /api/plans` — create or update a plan
- `DELETE /api/plans/{id}` — delete a plan

The API writes atomically and keeps the previous JSON as `.backup`.

## Security

This version intentionally uses a local JSON store rather than a database or cloud service. If the web service is exposed beyond a trusted network, add authentication and restrict write access to `/api/plans` before exposing it publicly.


### Demand surcharge

The plan editor can enable a **monthly peak demand surcharge** for Flat, TOU and Wholesale plans.

Configure:

- demand rate as **$/kW/day** (for example `$0.25/kW/day` = `25c/kW/day`)
- one or more demand windows
- weekdays for each window
- optional months for seasonal demand windows
- start and end times

For each calendar month, the calculator finds the highest complete 30-minute import block within the demand window(s). A 30-minute block is converted to average demand using `kWh × 2`, then the monthly charge is: `peak kW × demand rate × calendar days in month`.

This matches the structure described by Momentum Energy for demand tariffs: the highest half-hour during the demand window sets the month's demand charge, with the basic tariff calculation multiplying peak demand by the demand rate and number of days in the month.

The result reports the monthly peak block, date/time, kWh, kW, selected demand window and calculated charge. For incomplete uploaded months, the peak is still based only on available meter data, while the configured tariff rate is multiplied by the full calendar days in that month; the detail makes this visible.

Older plans using `rate_dollars_per_kw` remain readable. If no demand windows are present, they are treated as an all-day window for backwards compatibility; new plans should explicitly configure the applicable demand window(s).
