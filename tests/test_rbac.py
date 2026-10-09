"""Tests for role-based access control."""

from app import models


def test_customer_cannot_accept_booking(
    client, customer_token, db_session, beautician, customer
):
    """Customers cannot accept bookings (beautician-only action)."""
    booking = models.Booking(
        user_id=customer.id,
        beautician_id=beautician.id,
        service_id=None,
        status="Requested",
    )
    db_session.add(booking)
    db_session.commit()
    db_session.refresh(booking)

    response = client.put(
        f"/booking/{booking.id}/accept",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert response.status_code == 403
    assert "Only beauticians" in response.json()["detail"]


def test_beautician_cannot_create_booking(
    client, beautician_token, service
):
    """Beauticians cannot create bookings (customer-only action)."""
    response = client.post(
        "/booking",
        json={"service_id": service.id},
        headers={"Authorization": f"Bearer {beautician_token}"},
    )
    assert response.status_code == 403
    assert "Only customers" in response.json()["detail"]


def test_customer_cannot_view_admin_routes(
    client, customer_token
):
    """Customers cannot access admin endpoints."""
    response = client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert response.status_code == 403


def test_beautician_cannot_view_admin_routes(
    client, beautician_token
):
    response = client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {beautician_token}"},
    )
    assert response.status_code == 403


def test_admin_can_view_admin_routes(
    client, admin_token
):
    response = client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200