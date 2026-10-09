"""
Test that Redis distributed locking prevents double-booking.

This is the highest-value test in the suite: it verifies the resume
claim that concurrent booking requests for the same beautician result
in exactly one success.
"""

import concurrent.futures

from app import models


def test_concurrent_bookings_only_one_succeeds(
    client, customer_token, db_session, beautician, service
):
    """
    Spawn two simultaneous booking requests for the same beautician.

    Exactly one must succeed (201), the other must fail (404, no
    available beautician) because the Redis lock serializes them.
    """
    def attempt_booking():
        return client.post(
            "/booking",
            json={
                "beautician_id": beautician.id,
                "service_id": service.id,
            },
            headers={"Authorization": f"Bearer {customer_token}"},
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(attempt_booking)
        f2 = executor.submit(attempt_booking)
        r1 = f1.result()
        r2 = f2.result()

    statuses = sorted([r1.status_code, r2.status_code])

    # Exactly one succeeds, exactly one fails
    assert statuses == [201, 404], (
        f"Expected one success and one failure, got {statuses}. "
        f"Responses: {r1.json()}, {r2.json()}"
    )

    # Only one booking should exist for this beautician
    bookings = (
        db_session.query(models.Booking)
        .filter(models.Booking.beautician_id == beautician.id)
        .all()
    )
    assert len(bookings) == 1


def test_lock_released_after_booking(
    client, customer_token, db_session, beautician, service
):
    """
    After a booking, the Redis lock must be released. Otherwise, the
    next booking attempt would fail.
    """
    # First booking
    r1 = client.post(
        "/booking",
        json={
            "beautician_id": beautician.id,
            "service_id": service.id,
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert r1.status_code == 201

    # Manually release beautician (simulate completion)
    beautician.is_available = True
    db_session.commit()

    # Second booking for the same beautician should succeed
    r2 = client.post(
        "/booking",
        json={
            "beautician_id": beautician.id,
            "service_id": service.id,
        },
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert r2.status_code == 201