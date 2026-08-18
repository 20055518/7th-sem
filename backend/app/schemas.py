from enum import Enum

from pydantic import BaseModel, Field


class UserRole(str, Enum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    RECEPTION = "reception"
    ADMIN = "admin"


class UserCreate(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class StaffUserCreate(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole


class UserLogin(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    email: str
    role: UserRole