"""Pydantic models / API schemas for hospital queue system.
These models validate inbound/outbound data. MongoDB document validators
are applied at init_db() time (see db.py)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field, validator


# ---------------------------------------------------------------------------
# Common / shared
# ---------------------------------------------------------------------------

class TimestampedBase(BaseModel):
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)


class PyObjectId(str):
    """Wrapper so API accepts / returns ObjectId as string."""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        return str(v)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class UserBase(BaseModel):
    email: str = Field(..., min_length=1, max_length=254)
    full_name: Optional[str] = None
    role: Literal["patient", "receptionist", "doctor", "admin"]


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserInDB(UserBase):
    hashed_password: str
    is_active: bool = True


class UserPublic(BaseModel):
    id: str = "..."  # placeholder; actual ObjectId serialized at API boundary
    email: str
    full_name: Optional[str]
    role: str


# ---------------------------------------------------------------------------
# Departments
# ---------------------------------------------------------------------------

class DepartmentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    code: Optional[str] = None  # e.g., "CRD", "CARDIOLOGY"


class DepartmentCreate(DepartmentBase):
    pass


class Department(DepartmentBase):
    id: str
    createdAt: datetime
    updatedAt: datetime


# ---------------------------------------------------------------------------
# Rooms
# ---------------------------------------------------------------------------

class RoomBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    capacity: int = Field(default=1, ge=1)


class RoomCreate(RoomBase):
    pass


class Room(RoomBase):
    id: str
    departmentId: str
    createdAt: datetime
    updatedAt: datetime


# ---------------------------------------------------------------------------
# Doctors
# ---------------------------------------------------------------------------

class DoctorBase(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=120)
    departmentId: str
    title: Optional[str] = None  # e.g., "Professor", "Dr."


class DoctorCreate(DoctorBase):
    pass


class Doctor(DoctorBase):
    id: str
    userId: Optional[str] = None  # linked JWT user ID, if any
    createdAt: datetime
    updatedAt: datetime


# ---------------------------------------------------------------------------
# Patients
# ---------------------------------------------------------------------------

class PatientBase(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=120)
    medical_record_number: Optional[str] = None
    departmentId: Optional[str] = None


class PatientCreate(PatientBase):
    password: str  # bcrypt'd at reception sign-up


class Patient(PatientBase):
    id: str
    userId: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime


# ---------------------------------------------------------------------------
# Queue entries (the core queue lifecycle document)
# ---------------------------------------------------------------------------

class QueueEntryBase(BaseModel):
    patientId: str
    doctorId: str
    departmentId: str
    tokenNumber: str = Field(..., min_length=4, max_length=20)
    status: Literal["waiting", "called", "in_consultation", "completed", "skipped", "no_show", "absent"]
    position: int = Field(default=1, ge=1)


class QueueEntryCreate(QueueEntryBase):
    pass


class QueueEntry(QueueEntryBase, TimestampedBase):
    id: str
    predictedWait: Optional[float] = None  # minutes, from DHQPM
    checkedInAt: Optional[datetime] = None


# ---------------------------------------------------------------------------
# QR tokens (opaque, single-use, time-bound)
# ---------------------------------------------------------------------------

class QrTokenBase(BaseModel):
    tokenHash: str = Field(..., min_length=32, max_length=64)  # SHA-256 hex or custom
    queueEntryId: str
    purpose: Literal["check-in", "queue-access", "doctor-verification"] = "queue-access"


class QrTokenCreate(QrTokenBase):
    expiresAt: datetime


class QrToken(QrTokenBase, TimestampedBase):
    id: str
    usedAt: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Consultations
# ---------------------------------------------------------------------------

class ConsultationBase(BaseModel):
    queueEntryId: str
    startedAt: datetime
    completedAt: Optional[datetime] = None
    durationMinutes: Optional[float] = None
    outcome: Literal["normal", "early", "late", "no_show", "transferred"] = "normal"


class ConsultationCreate(ConsultationBase):
    pass


class Consultation(ConsultationBase, TimestampedBase):
    id: str


# ---------------------------------------------------------------------------
# ML predictions (snapshot of input + output for evaluation)
# ---------------------------------------------------------------------------

class MLPredictionBase(BaseModel):
    queueEntryId: str
    modelVersion: str = "dhqpm-0.1.0"
    inputFeatures: dict
    predictedWaitMinutes: float
    computedAt: datetime


class MLPrediction(MLPredictionBase, TimestampedBase):
    id: str


# ---------------------------------------------------------------------------
# Notifications (append-only, delivery tracking)
# ---------------------------------------------------------------------------

class NotificationBase(BaseModel):
    recipientUserId: str  # user ID of patient or staff
    type: Literal[
        "queue_joined",
        "queue_updated",
        "waiting_time_updated",
        "doctor_delayed",
        "you_are_next",
        "proceed_to_room",
        "qr_checked_in",
        "consultation_started",
        "consultation_completed",
    ]
    title: str
    message: str
    data: dict = {}  # payload: tokenNumber, position, etc.
    read: bool = False
    readAt: Optional[datetime] = None


class NotificationCreate(NotificationBase):
    pass


class Notification(NotificationBase, TimestampedBase):
    id: str


# ---------------------------------------------------------------------------
# Hospital routes (indoor navigation)
# ---------------------------------------------------------------------------

class HospitalRouteBase(BaseModel):
    departmentId: str
    floor: int
    room: str
    route: List[str]  # human-readable waypoints


class HospitalRouteCreate(HospitalRouteBase):
    pass


class HospitalRoute(HospitalRouteBase, TimestampedBase):
    id: str


# ---------------------------------------------------------------------------
# System settings (singleton-ish document)
# ---------------------------------------------------------------------------

class SystemSettingsBase(BaseModel):
    youAreNextThreshold: int = Field(default=2, ge=1, le=10)  # patients-ahead count
    notificationSettings: dict = Field(default_factory=dict)
    mlConfiguration: dict = Field(default_factory=dict)


class SystemSettings(SystemSettingsBase, TimestampedBase):
    id: str = "global_settings"