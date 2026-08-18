from datetime import datetime

from pydantic import BaseModel, Field


class QRTokenResponse(BaseModel):
    qr_image_data: str
    expires_at: datetime


class QRVerificationRequest(BaseModel):
    token: str = Field(min_length=20)


class QRVerificationResponse(BaseModel):
    valid: bool
    patient_email: str
    department: str
    token_number: int
    status: str