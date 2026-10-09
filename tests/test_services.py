"""Tests for the /services endpoint."""


def test_only_active_services_returned(
    client, customer_token, service, inactive_service
):
    response = client.get(
        "/services",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert response.status_code == 200

    returned_ids = [s["id"] for s in response.json()]
    assert service.id in returned_ids
    assert inactive_service.id not in returned_ids


def test_services_requires_auth(client):
    response = client.get("/services")
    assert response.status_code == 401


def test_create_service_requires_admin(
    client, customer_token
):
    response = client.post(
        "/admin/services",
        json={
            "name": "New Service",
            "description": "Test",
            "price": 1000,
            "duration": 60,
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert response.status_code == 403


def test_admin_can_create_service(
    client, admin_token
):
    response = client.post(
        "/admin/services",
        json={
            "name": "New Service",
            "description": "Test",
            "price": 1000,
            "duration": 60,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    assert response.json()["name"] == "New Service"