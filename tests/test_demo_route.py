from fastapi.testclient import TestClient

from overture.main import app

client = TestClient(app)


def test_ask_route_rejects_invalid_token_without_touching_db() -> None:
    # A garbage token should fail token verification and return 404
    # before the route ever reaches a database call -- this is provable
    # in a unit test with no live Postgres, because verify_share_token
    # fails synchronously, before `Depends(get_db)` would matter.
    response = client.post(
        "/api/v1/demo/not-a-real-token/ask",
        json={"question": "What is the renewal date?"},
    )
    assert response.status_code == 404
    assert "invalid" in response.json()["detail"].lower()


def test_ask_route_rejects_missing_question_field() -> None:
    response = client.post("/api/v1/demo/some-token/ask", json={})
    assert response.status_code == 422  # FastAPI's own request validation
