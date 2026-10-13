from enum import Enum

from pydantic import BaseModel, Field


# ============================================================
# QUEUE STATUS
# ============================================================

class QueueStatus(str, Enum):
    WAITING_FOR_TRIAGE = "waiting_for_triage"

    # Nurse has completed triage. Patient must now go to
    # reception for QR verification before entering the
    # active doctor queue.
    WAITING_FOR_RECEPTION = "waiting_for_reception"

    WAITING = "waiting"
    CALLED = "called"
    IN_CONSULTATION = "in_consultation"
    COMPLETED = "completed"
    SKIPPED = "skipped"


# ============================================================
# TRIAGE PRIORITY
# ============================================================

class TriagePriority(str, Enum):
    NORMAL = "normal"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


# ============================================================
# CREATE QUEUE ENTRY
# ============================================================

class QueueEntryCreate(BaseModel):
    patient_email: str | None = Field(default=None, min_length=5, max_length=254)
    department: str = Field(min_length=2, max_length=100)
    doctor_email: str | None = Field(default=None, max_length=254)


# ============================================================
# QUEUE RESPONSE
# ============================================================

class QueueEntryResponse(BaseModel):
    token_number: int
    patient_email: str
    department: str
    doctor_email: str | None
    status: QueueStatus
    position: int

    priority: TriagePriority = TriagePriority.NORMAL

    predicted_wait_minutes: float | None = None
    probability_short: float | None = None
    probability_moderate: float | None = None
    probability_long: float | None = None
    probability_very_long: float | None = None
    probability_long_or_more: float | None = None

    bayesian_state: str | None = None
    bayesian_expected_wait_minutes: float | None = None

    risk_level: str | None = None

    # True only after reception successfully verifies the
    # patient's queue QR for THIS queue entry.
    queue_access_verified: bool = False


# ============================================================
# PUBLIC QUEUE RESPONSE
# ============================================================

class PublicQueueEntryResponse(BaseModel):
    token_number: int
    department: str
    status: QueueStatus
    position: int


# ============================================================
# QUEUE STATUS UPDATE
# ============================================================

class QueueStatusUpdate(BaseModel):
    status: QueueStatus


# ============================================================
# NURSE ASSESSMENT CREATE
# ============================================================

class NurseAssessmentCreate(BaseModel):
    patient_email: str = Field(min_length=5, max_length=254)
    department: str = Field(min_length=2, max_length=100)
    doctor_email: str | None = Field(default=None, max_length=254)

    temperature: float | None = Field(default=None, ge=25, le=45)
    pulse: int | None = Field(default=None, ge=20, le=250)
    systolic_bp: int | None = Field(default=None, ge=50, le=250)
    diastolic_bp: int | None = Field(default=None, ge=30, le=150)
    spo2: float | None = Field(default=None, ge=50, le=100)
    pain_level: int | None = Field(default=None, ge=0, le=10)

    symptoms: str | None = Field(default=None, max_length=2000)
    nurse_notes: str | None = Field(default=None, max_length=4000)

    priority: TriagePriority = TriagePriority.NORMAL


# ============================================================
# NURSE ASSESSMENT RESPONSE
# ============================================================

class NurseAssessmentResponse(BaseModel):
    id: str
    patient_email: str
    department: str
    doctor_email: str | None
    temperature: float | None
    pulse: int | None
    systolic_bp: int | None
    diastolic_bp: int | None
    spo2: float | None
    pain_level: int | None
    symptoms: str | None
    nurse_notes: str | None
    priority: TriagePriority
    created_at: str
    updated_at: str
