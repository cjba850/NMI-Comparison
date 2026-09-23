
## v0.4 meter import

The supplied meter-export format is supported directly. The application is
grid-import-only for this use case: `Active Amt` is the authoritative energy
quantity. Solar/export billing is intentionally not modelled.

The AEMO API remains optional and is disabled by default. CSV upload does not
require AEMO credentials or certificates.
