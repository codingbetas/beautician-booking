from app.database import SessionLocal
from app.models import User, Beautician, Service
from app.auth import hash_password

db = SessionLocal()

# 1. Create a sample service with duration included
if not db.query(Service).first():
    service = Service(
        name="Hair Styling & Blowout", 
        description="Professional blowout and styling",
        price=1200, 
        duration=45,  # Added duration to satisfy NOT NULL constraint
        is_active=True
    )
    db.add(service)
    print("Added sample service.")

# 2. Create a beautician user & profile if none exists
if not db.query(Beautician).first():
    user = User(
        name="Priya Sharma", 
        email="priya@atoma.com", 
        password=hash_password("password123"), 
        role="beautician", 
        location="Mumbai"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    beautician = Beautician(
        user_id=user.id,
        name="Priya Sharma",
        location="Mumbai",
        is_available=True
    )
    db.add(beautician)
    print("Added sample beautician.")

db.commit()
db.close()
print("Database seeding completed successfully!")