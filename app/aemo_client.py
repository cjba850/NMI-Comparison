from __future__ import annotations

import csv
import io
import os
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from .engine import Interval, SYDNEY


DEFAULT_PROD_BASE_URL = "https://nem-apis.wgw.aemo.com.au/NEMRetail/cds-au/v1/secondary/energy"
DEFAULT_PREPROD_BASE_URL = "https://nem-apis.preprod.wgw.aemo.com.au/NEMRetail/cds-au/v1/secondary/energy"


class AemoApiError(RuntimeError):
    pass


@dataclass
class AemoNmiClient:
    """Client for AEMO's CDR electricity usage API.

    Access is not public consumer access: AEMO states that the CDR APIs are for
    Registered FRMPs servicing requests from Accredited Data Recipients and
    require AEMO registration, URM credentials and TLS certificates.
    """

    base_url: str = DEFAULT_PROD_BASE_URL
    participant_id: str | None = None
    username: str | None = None
    password: str | None = None
    cert: str | None = None
    key: str | None = None
    timeout: float = 60.0

    @classmethod
    def from_env(cls) -> "AemoNmiClient":
        environment = os.getenv("AEMO_ENV", "production").lower()
        default = DEFAULT_PREPROD_BASE_URL if environment in {"preprod", "pre-production", "test"} else DEFAULT_PROD_BASE_URL
        return cls(
            base_url=os.getenv("AEMO_CDR_BASE_URL", default).rstrip("/"),
            participant_id=os.getenv("AEMO_PARTICIPANT_ID"),
            username=os.getenv("AEMO_URM_USERNAME"),
            password=os.getenv("AEMO_URM_PASSWORD"),
            cert=os.getenv("AEMO_TLS_CERT"),
            key=os.getenv("AEMO_TLS_KEY"),
            timeout=float(os.getenv("AEMO_HTTP_TIMEOUT", "60")),
        )

    def _client(self) -> httpx.Client:
        if not self.participant_id or not self.username or not self.password:
            raise AemoApiError("AEMO API is not configured: set AEMO_PARTICIPANT_ID, AEMO_URM_USERNAME and AEMO_URM_PASSWORD")
        if bool(self.cert) != bool(self.key):
            raise AemoApiError("AEMO_TLS_CERT and AEMO_TLS_KEY must be supplied together")
        cert = (self.cert, self.key) if self.cert and self.key else None
        return httpx.Client(timeout=self.timeout, cert=cert, follow_redirects=True)

    def get_usage(
        self,
        nmi: str,
        start: date,
        end: date,
        interval_reads: str = "FULL",
        page_size: int = 1000,
    ) -> list[Interval]:
        if start > end:
            raise ValueError("start must be on or before end")
        if (end - start).days > 366:
            raise ValueError("A single request is limited to 366 days by this application; split longer ranges into yearly requests")
        interval_reads = interval_reads.upper()
        if interval_reads not in {"FULL", "MIN_30", "NONE"}:
            raise ValueError("interval_reads must be FULL, MIN_30 or NONE")
        if interval_reads == "NONE":
            raise ValueError("interval_reads=NONE does not provide interval consumption data")

        url = f"{self.base_url}/electricity/servicepoints/{nmi}/usage"
        params = {
            "oldest-date": start.isoformat(),
            "newest-date": end.isoformat(),
            "interval-reads": interval_reads,
            "page": 1,
            "page-size": min(max(page_size, 1), 1000),
        }
        headers = {
            "Accept": "application/json",
            "X-initiatingParticipantId": self.participant_id,
            "x-v": "1",
            "x-min-v": "1",
            "x-fapi-interaction-id": str(uuid.uuid4()),
            "User-Agent": "nmi-energy-calculator/0.3",
        }

        all_intervals: list[Interval] = []
        with self._client() as client:
            while True:
                response = client.get(url, params=params, headers=headers, auth=(self.username, self.password))
                if response.status_code >= 400:
                    detail = _api_error_detail(response)
                    raise AemoApiError(f"AEMO API HTTP {response.status_code}: {detail}")
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise AemoApiError("AEMO API returned a non-JSON response") from exc

                all_intervals.extend(_extract_intervals(payload))
                next_link = _next_link(payload)
                if next_link:
                    url = next_link
                    params = {}
                    continue

                meta = payload.get("meta") if isinstance(payload, dict) else None
                total_pages = meta.get("totalPages") if isinstance(meta, dict) else None
                current_page = meta.get("currentPage") if isinstance(meta, dict) else params.get("page")
                if total_pages and current_page and int(current_page) < int(total_pages):
                    params["page"] = int(current_page) + 1
                    continue
                break

        if not all_intervals:
            raise AemoApiError("AEMO API returned no interval usage records for the requested NMI/date range")
        return sorted(all_intervals, key=lambda x: (x.timestamp, x.register))


def _api_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
        if isinstance(payload, dict):
            errors = payload.get("errors")
            if isinstance(errors, list) and errors:
                first = errors[0]
                if isinstance(first, dict):
                    return str(first.get("detail") or first.get("title") or first)
            return str(payload.get("message") or payload.get("error") or payload)
    except ValueError:
        pass
    return response.text[:500]


def _next_link(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    links = payload.get("links") or {}
    if isinstance(links, dict):
        return links.get("next")
    return None


def _extract_intervals(payload: Any) -> list[Interval]:
    """Extract CDR interval reads while tolerating minor schema/wrapper changes."""
    records: list[tuple[dict[str, Any], str]] = []

    def walk(value: Any, inherited_register: str = "import") -> None:
        if isinstance(value, dict):
            register = str(_first(value, "registerSuffix", "registerId", "register", default=inherited_register))
            keys = {str(k).lower() for k in value}
            has_time = any(k in keys for k in {"intervalstartdatetime", "readstartdatetime", "startdatetime", "datetime", "timestamp"})
            has_value = any(k in keys for k in {"value", "readvalue", "usage", "kwh", "consumption"})
            if has_time and has_value:
                records.append((value, register))
            for child in value.values():
                walk(child, register)
        elif isinstance(value, list):
            for child in value:
                walk(child, inherited_register)

    walk(payload)

    out: list[Interval] = []
    seen: set[tuple[str, float, str]] = set()
    for record, inherited_register in records:
        ts_raw = _first(record, "intervalStartDateTime", "readStartDateTime", "startDateTime", "dateTime", "timestamp")
        value_raw = _first(record, "value", "readValue", "usage", "kwh", "consumption")
        if ts_raw is None or value_raw is None:
            continue
        try:
            ts = _parse_datetime(str(ts_raw))
            value = float(value_raw)
        except (TypeError, ValueError):
            continue
        if value < 0:
            continue
        register = str(_first(record, "registerSuffix", "registerId", "register", default=inherited_register))
        key = (ts.isoformat(), value, register)
        if key in seen:
            continue
        seen.add(key)
        out.append(Interval(ts, value, register))
    return out


def _first(record: dict[str, Any], *names: str, default: Any = None) -> Any:
    lower = {str(k).lower(): v for k, v in record.items()}
    for name in names:
        if name.lower() in lower:
            return lower[name.lower()]
    return default


def _parse_datetime(raw: str):
    from datetime import datetime

    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return (dt if dt.tzinfo else dt.replace(tzinfo=SYDNEY)).astimezone(SYDNEY)


def intervals_to_csv(intervals: list[Interval]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "kwh", "register"])
    for item in intervals:
        writer.writerow([item.timestamp.isoformat(), f"{item.kwh:.6f}", item.register])
    return output.getvalue()
