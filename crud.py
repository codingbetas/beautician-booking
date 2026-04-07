from models import User, Beautician, Booking
from auth import hash_password
from redis_conn import redis_client
import uuid 

VALID_TRANSITIONS = {
    "Requested": ["Accepted", "Cancelled"],
    "Accepted": ["In Progress", "Cancelled"],
    "In Progress": ["Completed"],
}

def create_user(db, email, password, role="user", location=None):
    user = User(email=email, password=hash_password(password), role=role, location=location)
    db.add(user)
    db.commit()
    db.refresh(user)   # ✅ ADD THIS
    return user


def create_beautician(db, name, location):
    b = Beautician(name=name, location=location, is_available=True)
    db.add(b)
    db.commit()
    db.refresh(b)
    return b

def create_booking(db, user_id):
    user = db.query(User).filter(User.id == user_id).first()

    # 1️⃣ Try to assign a beautician in the same location
    beauticians = db.query(Beautician).filter(
        Beautician.is_available == True,
        Beautician.location == user.location
    ).all()

    # 2️⃣ If none in same location, pick any available beautician
    if not beauticians:
        beauticians = db.query(Beautician).filter(
            Beautician.is_available == True
        ).all()

    for beautician in beauticians:
        lock_key = f"lock:beautician:{beautician.id}"
        lock_value = str(uuid.uuid4())

        lock = redis_client.set(lock_key, lock_value, nx=True, ex=10)
        if not lock:
            continue

        try:
            if not beautician.is_available:
                continue

            beautician.is_available = False

            booking = Booking(
                user_id=user_id,
                beautician_id=beautician.id,
                status="Requested"
            )

            db.add(booking)
            db.commit()
            db.refresh(booking)
            return booking

        finally:
            if redis_client.get(lock_key) == lock_value:
                redis_client.delete(lock_key)

    return None

def update_status(db, booking_id, status):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()

    if not booking:
        return {"error": "Booking not found"}

    current_status = booking.status

    if status not in VALID_TRANSITIONS.get(current_status, []):
        return {"error": f"Invalid transition from {current_status} to {status}"}

    booking.status = status

    if status == "Completed":
        beautician = db.query(Beautician).filter(
            Beautician.id == booking.beautician_id
        ).first()
        if beautician:
            beautician.is_available = True

    db.commit()
    db.refresh(booking)

    return booking