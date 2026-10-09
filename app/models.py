from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    location = Column(String, nullable=False)
    role = Column(String, default="user", nullable=False)


class Beautician(Base):
    __tablename__ = "beauticians"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String, nullable=False)
    location = Column(String, nullable=False)
    is_available = Column(Boolean, default=True)


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    price = Column(Integer, nullable=False)
    duration = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    beautician_id = Column(Integer, ForeignKey("beauticians.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=True)
    status = Column(String, default="Requested", nullable=False)
