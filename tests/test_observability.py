from overture.config import Settings


def test_app_insights_connection_string_defaults_to_none() -> None:
    # This is what keeps local dev and the entire test suite free of
    # any Azure Monitor network call -- main.py only wires OTel when
    # this is truthy. If this default ever silently changed to a
    # non-None value, every test run would start trying to configure
    # Azure Monitor, which would be a surprising and hard-to-diagnose
    # failure mode far from this one line.
    settings = Settings()
    assert settings.app_insights_connection_string is None


def test_app_boots_and_health_check_works_without_app_insights() -> None:
    # Import-time proof, not just a settings check: overture.main
    # constructs the FastAPI app and its conditional OTel block at
    # import time. If that block ever ran unconditionally, importing
    # this module in a test environment with no real connection
    # string would raise or hang trying to reach Azure.
    from fastapi.testclient import TestClient

    from overture.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
