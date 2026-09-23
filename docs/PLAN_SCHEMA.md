# Plan schema v0.3

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
