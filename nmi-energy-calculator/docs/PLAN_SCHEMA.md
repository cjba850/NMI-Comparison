# Plan schema v0.2

All plans:

```json
{
  "id":"unique-id",
  "provider":"Retailer",
  "name":"Plan name",
  "effective_from":"2026-01-01",
  "effective_to":null,
  "daily_supply_cents":110.0,
  "usage": {},
  "source_document":"",
  "source_url":"",
  "last_verified":"2026-09-23"
}
```

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

`margin_cents_per_kwh` and `other_cents_per_kwh` are retailer-plan assumptions and must be verified from the plan documentation.

The AEMO spot price is supplied separately because it varies by date and NEM region rather than being a fixed plan attribute.
