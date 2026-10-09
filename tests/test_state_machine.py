"""Tests for the 5-state booking state machine."""

from app import models


def _make_booking(db, customer, beautician, status="Requested"):
    booking = models.Booking(
        user_id=customer.id,
        beautician_id=beautician.id,
        service_id=None,
        status=status,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking


def test_invalid_transition_requested_to_completed(
    client, beautician_token, db_session, customer, beautician
):
    """Requested -> Completed must be rejected (skips intermediate states)."""
    booking = _make_booking(db_session, customer, beautician)

    response = client.put(
        f"/booking/{booking.id}/status",
        params={"new_status": "Completed"},
        headers={"Authorization": f"Bearer {beautician_token}"},
    )

    assert response.status_code == 403
    assert "Invalid transition" in response.json()["detail"]


def test_valid_transition_requested_to_accepted(
    client, beautician_token, db_session, customer, beautician
):
    booking = _make_booking(db_session, customer, beautician)

    response = client.put(
        f"/booking/{booking.id}/accept",
        headers={"Authorization": f"Bearer {beautician_token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "Accepted"


def test_full_lifecycle(
    client, beautician_token, db_session, customer, beautician
):
    """Requested -> Accepted -> In Progress -> Completed."""
    booking = _make_booking(db_session, customer, beautician)

    # Requested -> Accepted
    r = client.put(
        f"/booking/{booking.id}/accept",
        headers={"Authorization": f"Bearer {beautician_token}"},
    )
    assert r.status_code == 200

    # Accepted -> In Progress
    r = client.put(
        f"/booking/{booking.id}/status",
        params={"new_status": "In Progress"},
        headers={"Authorization": f"Bearer {beautician_token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "In Progress"

    # In Progress -> Completed
    r = client.put(
        f"/booking/{booking.id}/status",
        params={"new_status": "Completed"},
        headers={"Authorization": f"Bearer {beautician_token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "Completed"


def test_cannot_transition_from_completed(
    client, beautician_token, db_session, customer, beautician
):
    """Completed is terminal — no transitions allowed."""
    booking = _make_booking(
        db_session, customer, beautician, status="Completed"
    )

    response = client.put(
        f"/booking/{booking.id}/status",
        params={"new_status": "Accepted"},
        headers={"Authorization": f"Bearer {beautician_token}"},
    )

    assert response.status_code == 403
    assert "Invalid transition" in response.json()["detail"]


def test_completing_booking_releases_beautician(
    client, beautician_token, db_session, customer, beautician
):
    """When booking completes, beautician becomes available again."""
    beautician.is_available = False
    db_session.commit()

    booking = _make_booking(
        db_session, customer, beautician, status="In Progress"
    )

    response = client.put(
        f"/booking/{booking.id}/status",
        params={"new_status": "Completed"},
        headers={"Authorization": f"Bearer {beautician_token}"},
    )

    assert response.status_code == 200

    db_session.refresh(beautician)
    assert beautician.is_available is True