# database.py already has
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import create_engine

DATABASE_URL = "sqlite:///./atoma.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

# dependency function
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()