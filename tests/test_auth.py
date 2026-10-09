"""Tests for signup, login, and JWT-protected routes."""


def test_signup_creates_user(client):
    response = client.post(
        "/signup",
        json={
            "name": "Alice",
            "email": "alice@example.com",
            "password": "password123",
            "role": "user",
            "location": "Mumbai",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "alice@example.com"
    assert data["role"] == "user"


def test_signup_duplicate_email_rejected(client, customer):
    response = client.post(
        "/signup",
        json={
            "name": "Duplicate",
            "email": customer.email,
            "password": "password123",
            "role": "user",
            "location": "Mumbai",
        },
    )
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


def test_signup_cannot_create_admin(client):
    response = client.post(
        "/signup",
        json={
            "name": "Hacker",
            "email": "hacker@example.com",
            "password": "password123",
            "role": "admin",
            "location": "Mumbai",
        },
    )
    assert response.status_code == 400
    assert "Invalid account type" in response.json()["detail"]


def test_login_returns_token(client, customer):
    response = client.post(
        "/login",
        data={
            "username": customer.email,
            "password": "password123",
        },
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"


def test_login_wrong_password_rejected(client, customer):
    response = client.post(
        "/login",
        data={
            "username": customer.email,
            "password": "wrongpassword",
        },
    )
    assert response.status_code == 401


def test_protected_route_requires_token(client):
    response = client.get("/me")
    assert response.status_code == 401


def test_protected_route_works_with_token(client, customer_token):
    response = client.get(
        "/me",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "customer@test.com"