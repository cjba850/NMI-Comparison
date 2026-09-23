import pytest
from app.aemo_config import aemo_api_enabled, require_aemo_enabled

def test_aemo_disabled_by_default(monkeypatch):
    monkeypatch.delenv("AEMO_API_ENABLED", raising=False)
    assert aemo_api_enabled() is False

def test_aemo_can_be_enabled(monkeypatch):
    monkeypatch.setenv("AEMO_API_ENABLED", "true")
    assert aemo_api_enabled() is True

def test_disabled_integration_fails_clearly(monkeypatch):
    monkeypatch.setenv("AEMO_API_ENABLED", "false")
    with pytest.raises(RuntimeError):
        require_aemo_enabled()
