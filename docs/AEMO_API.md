# Optional AEMO API integration

The AEMO API connector is optional and disabled by default.

Normal users can upload their meter CSV and use all tariff/calculation functions
without AEMO credentials, certificates, or API access.

Set `AEMO_API_ENABLED=true` only on a deployment with the appropriate AEMO
participant/CDR access. The API integration is deliberately isolated from the
normal import/calculation pipeline.
