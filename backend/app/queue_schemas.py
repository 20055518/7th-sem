from enum import Enum

from pydantic import BaseModel, Field


class QueueStatus(str, Enum):
    WAITING = "waiting"
    CALLED = "called"
    IN_CONSULTATION = "in_consultation"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class QueueEntryCreate(BaseModel):
    patient_email: str = Field(min_length=5, max_length=254)
    department: str = Field(min_length=2, max_length=100)
    doctor_email: str | None = Field(default=None, max_length=254)


class QueueEntryResponse(BaseModel):
    token_number: int
    patient_email: str
    department: str
    doctor_email: str | None
    status: QueueStatus
    position: int

class QueueStatusUpdate(BaseModel):
    status: QueueStatus