from datetime import date

import pytest

from app.aemo_client import AemoApiError, AemoNmiClient, _extract_intervals, intervals_to_csv


def test_extract_cdr_interval_reads():
    payload = {
        "data": {
            "usage": [
                {
                    "servicePointId": "2001234567",
                    "readStartDate": "2025-01-01",
                    "readUType": "intervalRead",
                    "registerSuffix": "E1",
                    "unitOfMeasure": "KWH",
                    "intervalReads": [
                        {"intervalStartDateTime": "2025-01-01T00:00:00+11:00", "value": 0.42},
                        {"intervalStartDateTime": "2025-01-01T00:05:00+11:00", "value": 0.18},
                    ],
                }
            ]
        }
    }
    intervals = _extract_intervals(payload)
    assert len(intervals) == 2
    assert intervals[0].kwh == 0.42
    assert intervals[0].register == "E1"


def test_download_csv_format():
    client = AemoNmiClient()
    from app.engine import Interval, SYDNEY
    from datetime import datetime
    data = intervals_to_csv([Interval(datetime(2025, 1, 1, tzinfo=SYDNEY), 1.25, "E1")])
    assert data.splitlines()[0] == "timestamp,kwh,register"
    assert "1.250000" in data


def test_client_requires_credentials():
    with pytest.raises(AemoApiError, match="not configured"):
        AemoNmiClient().get_usage("2001234567", date(2025, 1, 1), date(2025, 1, 1))
