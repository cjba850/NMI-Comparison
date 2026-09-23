# Plan schema v0.11

All plans:

```json
{
  "id":"unique-id",
  "provider":"Retailer",
  "name":"Plan name",
  "effective_from":"2026-01-01",
  "effective_to":null,
  "daily_supply_dollars":1.10,
  "monthly_subscription_dollars":0.0,
  "controlled_load": {
    "cl1_cents_per_kwh":null,
    "cl2_cents_per_kwh":null
  },
  "usage": {},
  "source_document":"",
  "source_url":"",
  "last_verified":"2026-09-23"
}
```

`daily_supply_dollars` is a fixed supply charge in dollars per calendar day. It is not a rate per kWh.

`monthly_subscription_dollars` is an optional fixed monthly fee, useful for wholesale/spot plans that charge for access to the product. It is applied once for each calendar month represented by the uploaded meter data.

## Flat

```json
"usage": {"type":"flat", "cents_per_kwh":30.0}
```

## TOU

```json
"usage": {
  "type":"tou",
  "periods":[
    {"name":"peak","days":[0,1,2,3,4],"start":"14:00","end":"20:00","cents_per_kwh":42.0}
  ]
}
```

Python weekday numbers are Monday=0 through Sunday=6.

## Wholesale

```json
"usage": {
  "type":"wholesale",
  "margin_cents_per_kwh":8.0,
  "other_cents_per_kwh":0.0
}
```

The wholesale subscription is stored at plan level using `monthly_subscription_dollars`.

## Controlled load

Some plans have separate CL1 and/or CL2 rates. These are stored as optional c/kWh values. The current meter export format supplied for this project reports total active import (`Active Amt`) but does not provide separate CL1/CL2 kWh, so those rates cannot be charged accurately and are deliberately excluded from the calculated total. The dashboard notes their presence.

## Optional monthly peak demand surcharge

Demand is a plan-level charge and can therefore be enabled for any plan type (`flat`, `tou`, or `wholesale`):

```json
"demand": {
  "enabled": true,
  "rate_dollars_per_kw_per_day": 0.25,
  "windows": [
    {
      "name": "Weekday peak",
      "days": [0,1,2,3,4],
      "months": [12,1,2,3],
      "start": "17:00",
      "end": "20:00"
    }
  ]
}
```

For each calendar month, the calculator finds the highest **complete 30-minute import block** whose start time falls inside one of the configured demand windows. A 30-minute block containing `5.0 kWh` represents `10.0 kW` of average demand (`5.0 × 2`). The monthly demand charge is then:

```text
peak kW × demand rate ($/kW/day) × calendar days in month
```

For example, `10 kW × $0.25/kW/day × 31 days = $77.50` for January.

Demand windows support the same weekday numbering as TOU periods (Monday=0 through Sunday=6) and optional month restrictions. Multiple windows allow seasonal structures such as summer and winter demand periods.

For 5-minute or 15-minute meter data, intervals are aggregated into aligned 30-minute blocks. Incomplete blocks are excluded. The resulting monthly demand charge is reported separately as `demand_cost`, with per-month detail in `demand.months`.

For backwards compatibility, `rate_dollars_per_kw` is still accepted as an alias and an enabled demand definition with no windows is treated as an all-day demand window. New plans should use `rate_dollars_per_kw_per_day` and explicit demand windows.
