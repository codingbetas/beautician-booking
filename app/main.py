"""
Atoma Beauty Booking API.

FastAPI application for managing beautician bookings with
JWT authentication, role-based access control, and Redis-backed
distributed locking to prevent double-booking.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas, crud
from app.auth import (
    create_token,
    verify_password,
    get_current_user,
    require_admin,
)


# --------------------------------------------------
# LOGGING
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("atoma.api")


# --------------------------------------------------
# LIFESPAN
# --------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan. Schema is managed by Alembic migrations
    (run `alembic upgrade head` before starting the app).
    """
    logger.info("Application starting.")
    yield
    logger.info("Application shutting down.")

# --------------------------------------------------
# APP
# --------------------------------------------------

app = FastAPI(
    title="Atoma Beauty Booking API",
    version="1.0.0",
    description=(
        "A booking platform for beauticians with JWT auth, RBAC, "
        "a 5-state booking machine, and Redis distributed locking."
    ),
    lifespan=lifespan,
)


# --------------------------------------------------
# CORS
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================================================
# HEALTH
# ==================================================

@app.get("/", tags=["Health"])
def root():
    return {"message": "Atoma Beauty API is running"}


# ==================================================
# AUTHENTICATION
# ==================================================

@app.post(
    "/signup",
    response_model=schemas.UserOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Auth"],
)
def signup(
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
):
    """
    Register a new user.

    Only `user` and `beautician` roles are allowed via public signup.
    Admin accounts must be created out-of-band.
    """
    existing = (
        db.query(models.User)
        .filter(models.User.email == user.email)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    if user.role not in ("user", "beautician"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid account type",
        )

    return crud.create_user(
        db,
        user.name,
        user.email,
        user.password,
        user.role,
        user.location,
    )


@app.post("/login", tags=["Auth"])
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Exchange email + password for a JWT access token.
    """
    db_user = (
        db.query(models.User)
        .filter(models.User.email == form_data.username)
        .first()
    )

    if not db_user or not verify_password(
        form_data.password, db_user.password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_token({
        "sub": db_user.email,
        "role": db_user.role,
    })

    return {"access_token": token, "token_type": "bearer"}


@app.get(
    "/me",
    response_model=schemas.UserOut,
    tags=["Auth"],
)
def get_me(
    current_user: models.User = Depends(get_current_user),
):
    """Return the currently authenticated user."""
    return current_user


# ==================================================
# BEAUTICIANS
# ==================================================

@app.post(
    "/beautician",
    response_model=schemas.BeauticianOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Beauticians"],
)
def create_beautician(
    b: schemas.BeauticianCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Create a beautician profile for the authenticated beautician."""
    if current_user.role != "beautician":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only beauticians can create a beautician profile",
        )

    return crud.create_beautician(
        db, current_user, b.name, b.location
    )


@app.get(
    "/beauticians",
    response_model=list[schemas.BeauticianOut],
    tags=["Beauticians"],
)
def get_beauticians(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List all currently available beauticians."""
    if current_user.role not in ("user", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers and admins can view beauticians",
        )

    return (
        db.query(models.Beautician)
        .filter(models.Beautician.is_available == True)  # noqa: E712
        .all()
    )


@app.put(
    "/beautician/availability",
    response_model=schemas.BeauticianOut,
    tags=["Beauticians"],
)
def update_availability(
    available: bool,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Toggle the authenticated beautician's availability."""
    if current_user.role != "beautician":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only beauticians can change availability",
        )

    beautician = (
        db.query(models.Beautician)
        .filter(models.Beautician.user_id == current_user.id)
        .first()
    )

    if not beautician:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Beautician profile not found",
        )

    beautician.is_available = available
    db.commit()
    db.refresh(beautician)

    return beautician


# ==================================================
# BOOKINGS
# ==================================================

@app.post(
    "/booking",
    response_model=schemas.BookingOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Bookings"],
)
def create_booking(
    booking: schemas.BookingCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Create a booking.

    - If `beautician_id` is provided, that specific beautician is booked.
    - Otherwise, the first available beautician in the customer's
      location is auto-assigned.

    Redis locking prevents concurrent bookings for the same beautician.
    """
    if current_user.role != "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can create bookings",
        )

    # Pre-validate the service (better error messages than 404-from-CRUD)
    if booking.service_id is not None:
        service = (
            db.query(models.Service)
            .filter(models.Service.id == booking.service_id)
            .first()
        )
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service not found",
            )
        if not service.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Service is currently unavailable",
            )

    result = crud.create_booking(
        db,
        current_user.id,
        beautician_id=booking.beautician_id,
        service_id=booking.service_id,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No available beautician for the requested booking",
        )

    logger.info(
        "Booking %s created by user %s for beautician %s",
        result.id,
        current_user.id,
        result.beautician_id,
    )

    return result


@app.get(
    "/bookings",
    response_model=list[schemas.BookingOut],
    tags=["Bookings"],
)
def list_bookings(
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    List bookings visible to the current user.

    - Customers see their own bookings.
    - Beauticians see bookings assigned to them.
    - Admins see everything.
    """
    query = db.query(models.Booking)

    if current_user.role == "user":
        query = query.filter(
            models.Booking.user_id == current_user.id
        )

    elif current_user.role == "beautician":
        beautician = (
            db.query(models.Beautician)
            .filter(models.Beautician.user_id == current_user.id)
            .first()
        )
        if not beautician:
            return []
        query = query.filter(
            models.Booking.beautician_id == beautician.id
        )

    elif current_user.role != "admin":
        return []

    if status_filter:
        query = query.filter(
            models.Booking.status == status_filter
        )

    return query.all()


@app.put(
    "/booking/{booking_id}/status",
    response_model=schemas.BookingOut,
    tags=["Bookings"],
)
def update_booking_status(
    booking_id: int,
    new_status: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Transition a booking's status.

    Only valid transitions are allowed (see `crud.VALID_TRANSITIONS`).
    Customers cannot change status; beauticians can only manage
    their own bookings; admins can do anything.
    """
    result = crud.update_status(
        db,
        booking_id,
        new_status,
        current_user,
    )

    if isinstance(result, dict) and "error" in result:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=result["error"],
        )

    return result


@app.put(
    "/booking/{booking_id}/accept",
    response_model=schemas.BookingOut,
    tags=["Bookings"],
)
def accept_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Beautician accepts a Requested booking.
    """
    if current_user.role != "beautician":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only beauticians can accept bookings",
        )

    result = crud.update_status(
        db,
        booking_id,
        "Accepted",
        current_user,
    )

    if isinstance(result, dict) and "error" in result:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=result["error"],
        )

    return result


# ==================================================
# ADMIN
# ==================================================

@app.get("/admin/users", tags=["Admin"])
def admin_list_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_admin(current_user)
    return db.query(models.User).all()


@app.get("/admin/beauticians", tags=["Admin"])
def admin_list_beauticians(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_admin(current_user)
    return db.query(models.Beautician).all()


@app.get("/admin/bookings", tags=["Admin"])
def admin_list_bookings(
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_admin(current_user)

    query = db.query(models.Booking)
    if status_filter:
        query = query.filter(
            models.Booking.status == status_filter
        )
    return query.all()


@app.post(
    "/admin/services",
    response_model=schemas.ServiceOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Admin"],
)
def admin_create_service(
    service: schemas.ServiceCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    require_admin(current_user)

    new_service = models.Service(
        name=service.name,
        description=service.description,
        price=service.price,
        duration=service.duration,
        is_active=True,
    )
    db.add(new_service)
    db.commit()
    db.refresh(new_service)
    return new_service


# ==================================================
# SERVICES (public read)
# ==================================================

@app.get(
    "/services",
    response_model=list[schemas.ServiceOut],
    tags=["Services"],
)
def list_services(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List all active services."""
    return (
        db.query(models.Service)
        .filter(models.Service.is_active == True)  # noqa: E712
        .all()
    )