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


def test_cors_allows_the_vite_dev_server_origin_in_local_env() -> None:
    # Regression test for a real bug found via an actual browser
    # (D-0044): FastAPI's TestClient and curl never enforce CORS, so
    # this route's CORS behavior was completely unverified until a
    # real browser hit it in session 9 and failed. This test sends a
    # real Origin header, the same way a browser preflight would, and
    # checks the server actually reflects it back as allowed.
    from fastapi.testclient import TestClient

    from overture.main import app

    client = TestClient(app)
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_does_not_allow_an_arbitrary_origin() -> None:
    from fastapi.testclient import TestClient

    from overture.main import app

    client = TestClient(app)
    response = client.get("/health", headers={"Origin": "http://evil.example.com"})
    assert "access-control-allow-origin" not in response.headers
