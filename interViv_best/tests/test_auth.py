from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from backend.main import app


def test_auth_signup_login_me_round_trip():
    client = TestClient(app)
    email = f"phase2-{uuid4().hex}@example.com"
    password = "correct-horse-battery-1"

    signup = client.post(
        "/auth/signup",
        json={"email": email, "password": password, "name": "Phase Two"},
    )
    assert signup.status_code == 200
    signup_body = signup.json()
    assert signup_body["token_type"] == "bearer"
    assert signup_body["user"]["email"] == email
    assert signup_body["access_token"]

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["user"]["email"] == email


def test_auth_signup_rejects_password_without_number():
    client = TestClient(app)
    email = f"phase2-{uuid4().hex}@example.com"

    response = client.post(
        "/auth/signup",
        json={"email": email, "password": "correcthorse", "name": "Phase Two"},
    )

    assert response.status_code == 422
    assert "letter and one number" in response.json()["detail"]
