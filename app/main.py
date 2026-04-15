from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database import SessionLocal, Base, engine
import models, schemas, crud
from auth import create_token, verify_password, get_current_user, hash_password
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)
app = FastAPI()

# DB dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Signup ---
@app.post("/signup", response_model=schemas.UserOut)
def signup(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db, user.email, user.password, user.role, user.location)

# --- Login (new: OAuth2PasswordRequestForm) ---
@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not db_user or not verify_password(form_data.password, db_user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token({"sub": db_user.email})
    return {"access_token": token, "token_type": "bearer"}

# --- Beautician ---
@app.post("/beautician")
def create_beautician(
    b: schemas.BeauticianCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)  # automatic token check
):
    if current_user.role != "beautician":
        raise HTTPException(status_code=403, detail="Only beauticians allowed")
    return crud.create_beautician(db, b.name, b.location)

# --- Booking ---
@app.post("/booking", response_model=schemas.BookingOut)
def book(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    booking = crud.create_booking(db, current_user.id)
    if not booking:
        raise HTTPException(status_code=404, detail="No beautician available")
    logger.info(f"Booking created successfully : {booking.id}")
    return booking

# --- Booking status ---
@app.put("/booking/{id}/status")
def update(id: int, status: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    result = crud.update_status(db, id, status)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.put("/booking/{id}/accept")
def accept_booking(
    id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role != "beautician":
        raise HTTPException(status_code=403, detail="Only beauticians can accept")
    return crud.update_status(db, id, "Accepted")

# --- Admin ---
@app.get("/admin/bookings")
def get_all(status: str = None, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    query = db.query(models.Booking)
    if status:
        query = query.filter(models.Booking.status == status)
    return query.all()