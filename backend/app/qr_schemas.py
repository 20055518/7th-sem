from datetime import datetime
from pydantic import BaseModel, Field

class QRTokenResponse(BaseModel):
    qr_image_data: str
    verification_code: str
    manual_code: str
    expires_at: datetime

class QRVerificationRequest(BaseModel):
    token: str | None = None
    manual_code: str | None = None

class QRVerificationResponse(BaseModel):
    valid: bool
    patient_email: str
    department: str
    token_number: int
    status: str
