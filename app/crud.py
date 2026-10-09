from app.models import User, Beautician, Booking, Service
from app.auth import hash_password
from app.redis_conn import redis_client
import uuid


VALID_TRANSITIONS = {
    "Requested": ["Accepted", "Cancelled"],
    "Accepted": ["In Progress", "Cancelled"],
    "In Progress": ["Completed"],
}


# ==================================================
# USERS
# ==================================================

def create_user(
    db,
    name,
    email,
    password,
    role="user",
    location=None,
):
    user = User(
        name=name,
        email=email,
        password=hash_password(password),
        role=role,
        location=location,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


# ==================================================
# BEAUTICIANS
# ==================================================

def create_beautician(db, user, name, location):
    existing = (
        db.query(Beautician)
        .filter(
            Beautician.user_id == user.id
        )
        .first()
    )

    if existing:
        return existing

    beautician = Beautician(
        user_id=user.id,
        name=name,
        location=location,
        is_available=True,
    )

    db.add(beautician)
    db.commit()
    db.refresh(beautician)

    return beautician


# ==================================================
# BOOKINGS
# ==================================================

def create_booking(db, user_id, beautician_id=None, service_id=None):
    """
    Create a booking.

    - If beautician_id is provided, book that specific beautician.
    - If beautician_id is None, auto-assign the first available one.
    - Redis lock prevents concurrent bookings for the same beautician.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None

    # Validate service if provided
    if service_id is not None:
        service = db.query(Service).filter(
            Service.id == service_id,
            Service.is_active == True,
        ).first()
        if not service:
            return None

    # Determine candidate beauticians
    if beautician_id is not None:
        # Specific beautician requested
        beautician = db.query(Beautician).filter(
            Beautician.id == beautician_id,
        ).first()
        if not beautician:
            return None
        beauticians = [beautician]
    else:
        # Auto-assign: prefer same location, fall back to any
        beauticians = db.query(Beautician).filter(
            Beautician.is_available == True,
            Beautician.location == user.location,
        ).all()
        if not beauticians:
            beauticians = db.query(Beautician).filter(
                Beautician.is_available == True,
            ).all()

    # Try to lock and book
    for beautician in beauticians:
        lock_key = f"lock:beautician:{beautician.id}"
        lock_value = str(uuid.uuid4())

        # 60s TTL: well above p99 booking latency
        lock = redis_client.set(lock_key, lock_value, nx=True, ex=60)

        if not lock:
            continue  # another request holds the lock; try next beautician

        try:
            db.refresh(beautician)

            if not beautician.is_available:
                continue  # was taken since we queried

            beautician.is_available = False
            booking = Booking(
                user_id=user_id,
                beautician_id=beautician.id,
                service_id=service_id,
                status="Requested",
            )

            db.add(booking)
            db.commit()
            db.refresh(booking)

            return booking

        finally:
            # Release only our lock
            if redis_client.get(lock_key) == lock_value:
                redis_client.delete(lock_key)

    return None


# ==================================================
# BOOKING ACCESS
# ==================================================

def get_booking_for_user(
    db,
    booking_id,
    user,
):
    booking = (
        db.query(Booking)
        .filter(
            Booking.id == booking_id
        )
        .first()
    )

    if not booking:
        return None

    # Admin
    if user.role == "admin":
        return booking

    # Customer
    if user.role == "user":
        if booking.user_id == user.id:
            return booking

    # Beautician
    if user.role == "beautician":

        beautician = (
            db.query(Beautician)
            .filter(
                Beautician.user_id
                == user.id
            )
            .first()
        )

        if (
            beautician
            and booking.beautician_id
            == beautician.id
        ):
            return booking

    return None


# ==================================================
# BOOKING STATUS
# ==================================================

def update_status(
    db,
    booking_id,
    status,
    current_user,
):
    booking = get_booking_for_user(
        db,
        booking_id,
        current_user,
    )

    if not booking:
        return {
            "error":
            "Booking not found or access denied"
        }

    # ----------------------------------------------
    # Customers cannot change booking status
    # ----------------------------------------------

    if current_user.role == "user":
        return {
            "error":
            "Customers cannot change booking status"
        }

    # ----------------------------------------------
    # Beautician ownership
    # ----------------------------------------------

    if current_user.role == "beautician":

        beautician = (
            db.query(Beautician)
            .filter(
                Beautician.user_id
                == current_user.id
            )
            .first()
        )

        if (
            not beautician
            or booking.beautician_id
            != beautician.id
        ):
            return {
                "error":
                "You can only manage your own bookings"
            }

    # ----------------------------------------------
    # Validate transition
    # ----------------------------------------------

    current_status = booking.status

    if status not in VALID_TRANSITIONS.get(
        current_status,
        [],
    ):
        return {
            "error": (
                f"Invalid transition from "
                f"{current_status} to {status}"
            )
        }

    booking.status = status

    # ----------------------------------------------
    # Release beautician
    # ----------------------------------------------

    if status in [
        "Completed",
        "Cancelled",
    ]:

        beautician = (
            db.query(Beautician)
            .filter(
                Beautician.id
                == booking.beautician_id
            )
            .first()
        )

        if beautician:
            beautician.is_available = True

    db.commit()
    db.refresh(booking)

    return booking
