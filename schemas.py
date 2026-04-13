from pydantic import BaseModel, ConfigDict

class UserCreate(BaseModel):
    email: str
    password: str
    role: str = "user"
    location: str

class UserLogin(BaseModel):
    email: str
    password: str

class UserOut(BaseModel):
    id: int
    email: str
    location: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class BeauticianCreate(BaseModel):
    name: str
    location: str


class BookingCreate(BaseModel):
    user_id: int

class BookingOut(BaseModel):
    id: int
    user_id: int
    beautician_id: int
    status: str

    model_config = ConfigDict(from_attributes=True)
