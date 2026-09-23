# Meter CSV format

v0.4 supports the supplied grid-import-only meter export.

Required fields:
- `Interval Date/Time`
- `Active UOM`
- `Active Amt`

`Active Amt` is the authoritative grid consumption value. `Amt` is not used.

Supported active units:
- `KWH`
- `MWH` (converted to kWh)

The parser also retains:
- Role
- Part Description
- Read Quality
- Reactive Amt
- Apparent Amt
- Power Factor

The application does not model solar/export for this use case.
