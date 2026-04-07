from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True)
    password = Column(String)
    location = Column(String)
    role = Column(String, default="user")


class Beautician(Base):
    __tablename__ = "beauticians"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    location = Column(String)
    is_available = Column(Boolean, default=True)


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    beautician_id = Column(Integer, ForeignKey("beauticians.id"))
    status = Column(String, default="Requested")