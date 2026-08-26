from fastapi.testclient import TestClient

from overture.main import app

client = TestClient(app)


def test_extract_rejects_empty_transcript() -> None:
    response = client.post("/api/v1/sessions/extract", json={"transcript": "   "})
    assert response.status_code == 422
    assert "empty" in response.json()["detail"].lower()


def test_extract_rejects_missing_transcript_field() -> None:
    response = client.post("/api/v1/sessions/extract", json={})
    assert response.status_code == 422  # FastAPI's own request validation


def test_extract_runs_without_console_secret_by_default() -> None:
    # Auth is disabled by default (settings.console_shared_secret is
    # None in tests, same as local dev) -- proving the request reaches
    # past auth and hits the empty-transcript check, not a 401, is
    # what confirms auth is genuinely off rather than silently broken.
    response = client.post("/api/v1/sessions/extract", json={"transcript": ""})
    assert response.status_code != 401
