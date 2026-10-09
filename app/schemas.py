from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str = "user"
    location: str


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    location: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class BeauticianCreate(BaseModel):
    name: str
    location: str


class BeauticianOut(BaseModel):
    id: int
    user_id: int | None
    name: str
    location: str
    is_available: bool

    model_config = ConfigDict(from_attributes=True)


class ServiceCreate(BaseModel):
    name: str
    description: str | None = None
    price: int
    duration: int


class ServiceOut(BaseModel):
    id: int
    name: str
    description: str | None
    price: int
    duration: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class BookingCreate(BaseModel):
    beautician_id: int | None = None
    service_id: int | None = None


class BookingOut(BaseModel):
    id: int
    user_id: int
    beautician_id: int
    service_id: int | None
    status: str

    model_config = ConfigDict(from_attributes=True)
