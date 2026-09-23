# v0.2 Design

## Calculation pipeline

```text
NMI upload                    AEMO spot upload
     |                              |
     v                              v
NMI parser                    spot parser
     |                              |
     +---------- normalised --------+
                    |
                    v
              tariff engines
              /      |       \
            flat     TOU    wholesale
              \       |       /
               \      |      /
                    report
```

## Normalised data

NMI usage becomes `Interval(timestamp, kwh, register)` with timestamps normalised to `Australia/Sydney`.

Spot prices become `SpotPrice(timestamp, region, rrp_mwh)`.

## Engines

### Flat

```text
energy = Σ(kWh × flat c/kWh)
supply = days × daily supply c
```

### TOU

Each interval is assigned to the first matching tariff period by local weekday/time. Periods can be named `peak`, `shoulder`, `offpeak`, or any retailer-specific label.

### Wholesale

For five-minute NMI usage:

```text
interval cost = kWh × (RRP $/MWh ÷ 10 + margin c/kWh + other c/kWh)
```

For 30-minute NMI usage, the six five-minute RRP values are averaged before applying the interval kWh. This avoids inventing a within-interval load shape.

## Reporting model

The API returns:

- plan/provider/type
- annual usage
- energy cost
- supply cost
- total cost
- period breakdowns
- effective c/kWh
- comparison sorted by total cost
- wholesale region/margin/missing-price information
- calculation notes

The comparison is descriptive. The application should show the calculated figures rather than making a recommendation.

## Future tariff components

The data model should evolve toward:

```text
supply
+ import energy
+ demand
+ controlled load
+ network components
+ market/environmental components
- export/FIT credits
- discounts
- bill credits
```

Each component should be explicit and effective-dated rather than embedded in a single rate.
