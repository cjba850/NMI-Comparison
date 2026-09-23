# NMI Energy Plan Calculator v0.2

Self-hosted Australian electricity cost calculator for NMI interval exports.

Upload actual NMI usage and optionally an AEMO spot-price CSV, then compare the same usage against configurable **flat**, **time-of-use (TOU)** and **wholesale/spot** plans.

## What v0.2 adds

- Flat tariff engine
- TOU tariff engine with peak/shoulder/off-peak periods
- Wholesale/spot tariff engine
- AEMO spot-price CSV import
- NEM region selection (NSW1, VIC1, QLD1, SA1, TAS1)
- 5-minute spot-price alignment
- 30-minute NMI → six 5-minute spot-price averaging when 5-minute consumption is unavailable
- Comparison report sorted by annual total cost
- Effective c/kWh metric
- Wholesale margin and other per-kWh add-ons
- Calculation notes identifying wholesale assumptions/missing spot intervals
- Tests for flat, TOU, AEMO import and wholesale calculations

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Open `http://SERVER-IP:8080`.

The supplied tariffs are **fictional examples**. Replace them with rates verified against retailer Energy Price Fact Sheets or other authoritative tariff documents before using the calculator for a purchasing decision.

## Wholesale calculation model

AEMO publishes NEM spot/RRP data at five-minute resolution. The calculator expects RRP in **$/MWh** and converts it to cents/kWh. citeturn0search2turn0search0

For a 5-minute NMI dataset, each consumption interval is paired with its matching five-minute RRP. For a 30-minute NMI dataset, the application averages the six five-minute prices covering that 30-minute interval and applies that average to the interval's kWh. This is an explicit approximation that assumes usage is evenly distributed within the 30-minute interval.

The retail wholesale formula is conceptually:

```text
wholesale energy cost
  = consumption kWh × (AEMO RRP converted to c/kWh
                       + retailer margin c/kWh
                       + other configured c/kWh)

annual total
  = wholesale energy cost + daily supply charges
```

Network charges, environmental charges, market fees, demand charges, discounts, credits, controlled load and solar export are not silently inferred. Add them explicitly to a plan configuration as the model is extended.

## AEMO CSV input

The importer supports common AEMO-style `INTERVAL_DATETIME,REGIONID,RRP` data and `SETTLEMENTDATE,PERIODID,REGIONID,RRP` data, plus AEMO payloads containing header/data records where those fields are present. AEMO's data model identifies `TRADINGPRICE.RRP` as the regional reference price in $/MWh and describes five-minute spot pricing. citeturn0search0turn0search12

For reproducible annual analysis, use the final/appropriate historical AEMO price dataset for the same region and year as the NMI data.

## Plan configuration

Plans live in `data/plans.json`.

Flat:

```json
"usage": {"type":"flat", "cents_per_kwh":30.0}
```

TOU:

```json
"usage": {
  "type":"tou",
  "periods":[
    {"name":"peak","days":[0,1,2,3,4],"start":"14:00","end":"20:00","cents_per_kwh":42.0},
    {"name":"offpeak","days":[0,1,2,3,4,5,6],"start":"20:00","end":"14:00","cents_per_kwh":20.0}
  ]
}
```

Wholesale:

```json
"usage": {
  "type":"wholesale",
  "margin_cents_per_kwh":8.0,
  "other_cents_per_kwh":0.0
}
```

Recommended metadata:

```json
"source_document":"Retailer Energy Price Fact Sheet",
"source_url":"",
"last_verified":"2026-09-23"
```

## Important limitations

- The v0.2 engine treats uploaded intervals as import consumption.
- Solar export/FIT is not yet netted into annual cost.
- Demand charges are not yet implemented.
- Controlled-load registers are not yet separately priced.
- Discounts and bill credits are not yet implemented.
- A 30-minute NMI wholesale replay is an approximation; five-minute consumption data is preferable for wholesale comparison.
- AEMO spot price is not itself a complete retail electricity bill.

## Architecture

```text
NMI CSV ──> NMI parser ──> normalised intervals ──┐
                                                  ├─> tariff engine ─> report
AEMO CSV ─> spot parser ─> regional 5-min RRP ───┘       │
                                                        ├─ flat
                                                        ├─ TOU
                                                        └─ wholesale
```

The web service does not intentionally persist uploaded files.

## Deployment/security

See `docs/SYSTEMD.md`. Put the service behind a reverse proxy/HTTPS and authentication if exposed beyond a trusted LAN. The upload endpoints have request-size limits.

## References

- AEMO NEM Data Dashboard: current and historical five-minute spot pricing. citeturn0search2
- AEMO Electricity Data Model: `TRADINGPRICE.RRP` and five-minute spot-price definition. citeturn0search0turn0search12
- AEMO CSV data format overview. citeturn0search4
- Energy Made Easy: https://www.energymadeeasy.gov.au/
