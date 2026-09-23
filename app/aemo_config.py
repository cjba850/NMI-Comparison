import os

def aemo_api_enabled() -> bool:
    return os.getenv("AEMO_API_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }

def require_aemo_enabled():
    if not aemo_api_enabled():
        raise RuntimeError(
            "AEMO API integration is disabled. CSV upload is the standard data source."
        )
