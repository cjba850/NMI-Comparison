# Local plan management

Version 0.6 adds a browser interface for maintaining the electricity plans used by the calculator.

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
- Multiple TOU periods
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
