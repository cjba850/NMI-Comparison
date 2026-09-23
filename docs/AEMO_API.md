# AEMO NMI API integration

## Important access limitation

The application now includes an AEMO CDR usage connector, but AEMO does **not** expose arbitrary household NMI interval data through an unauthenticated public API.

AEMO's CDR API provides `getUsageForServicePoint` for up to 24 months of meter data for a single NMI. AEMO states that access is for Registered Financially Responsible Market Participants (FRMPs) servicing requests from Accredited Data Recipients, and requires AEMO registration, an MSATS/URM user and TLS certificates.

The application therefore keeps AEMO credentials on the server and never accepts them from the browser.

## Configuration

Copy `.env.example` to your deployment environment and set:

- `AEMO_PARTICIPANT_ID`
- `AEMO_URM_USERNAME`
- `AEMO_URM_PASSWORD`
- `AEMO_TLS_CERT`
- `AEMO_TLS_KEY`
- `AEMO_ENV=production` or `preprod`

The production CDR base URL is:

```text
https://nem-apis.wgw.aemo.com.au/NEMRetail/cds-au/v1/secondary/energy
```

Pre-production uses:

```text
https://nem-apis.preprod.wgw.aemo.com.au/NEMRetail/cds-au/v1/secondary/energy
```

AEMO specifies different TLS certificates for pre-production and production.

## API endpoint used by the application

```text
GET /electricity/servicepoints/{NMI}/usage
```

The connector requests:

- `oldest-date`
- `newest-date`
- `interval-reads=FULL` or `MIN_30`
- `page`
- `page-size`

The application supports AEMO pagination and converts returned interval reads into the same internal `Interval` model used by uploaded CSV data.

## Browser/API usage

```text
GET /api/aemo/nmi/{nmi}/usage?start=2025-01-01&end=2025-12-31&interval_reads=FULL
```

To download the normalised CSV used by the calculator:

```text
GET /api/aemo/nmi/{nmi}/download?start=2025-01-01&end=2025-12-31&interval_reads=FULL
```

The download is intentionally a simple `timestamp,kwh,register` CSV. It can be uploaded through the existing calculator UI and can also be retained as a reproducible snapshot of the API result.

## Security

Do not expose AEMO credentials or certificate paths through query parameters or the browser. Put the FastAPI service behind authentication if it is reachable outside a trusted LAN.

The application does not persist downloaded NMI data by default. The download endpoint streams a generated response.
