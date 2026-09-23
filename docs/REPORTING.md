# Reporting and recommendation model

## Historical replay

The application applies the same uploaded interval consumption to every configured plan. The result is a calculated historical cost, not a forecast.

## Usage statistics

The dashboard reports:

- total kWh
- days with data and coverage percentage
- average kWh/day
- maximum kWh/day
- minimum kWh/day
- median kWh/day
- P90 kWh/day
- monthly usage
- hourly usage profile

## Plan comparison

For each successfully calculated plan the report includes:

- provider and plan name
- tariff type
- energy cost
- supply cost
- total cost
- effective total cost per kWh
- difference from the lowest calculated cost

The comparison is sorted by calculated historical total cost.

## Recommendation

The recommendation identifies the plan with the lowest calculated historical cost and states the basis explicitly. It does not forecast future prices or guarantee future savings.

If the difference between the lowest and next-lowest calculated plans is below 2%, the dashboard calls out that the difference is small so non-price terms and future-price exposure can be considered.

## Incomplete data

If the uploaded year does not contain every calendar day, the report exposes the coverage percentage. An incomplete year should not be interpreted as a complete annual bill without further analysis.

Wholesale plans may also have missing AEMO spot intervals. Those are reported rather than silently treated as zero-price energy.
