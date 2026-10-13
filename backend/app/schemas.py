from enum import Enum

from pydantic import BaseModel, Field


# ============================================================
# USER ROLES
# ============================================================

class UserRole(str, Enum):

    PATIENT = "patient"

    DOCTOR = "doctor"

    NURSE = "nurse"

    RECEPTION = "reception"

    ADMIN = "admin"


# ============================================================
# PATIENT REGISTRATION
# ============================================================

class UserCreate(BaseModel):

    email: str = Field(
        min_length=5,
        max_length=254,
    )

    password: str = Field(
        min_length=8,
        max_length=128,
    )

    phone_number: str | None = Field(
        default=None,
        max_length=32,
    )

    sms_opt_in: bool = Field(
        default=False,
    )

    # Backwards compatibility alias if passed
    whatsapp_number: str | None = Field(
        default=None,
        max_length=32,
    )

    whatsapp_opt_in: bool = Field(
        default=False,
    )


# ============================================================
# PATIENT SMS PREFERENCES UPDATE
# ============================================================

class PatientSmsPreferencesUpdate(BaseModel):

    phone_number: str | None = Field(
        default=None,
        max_length=32,
    )

    sms_opt_in: bool = Field(
        default=False,
    )


class PatientSmsPreferencesResponse(BaseModel):

    phone_number: str | None = None

    sms_opt_in: bool = False


# ============================================================
# PATIENT FCM PUSH NOTIFICATION SCHEMAS
# ============================================================

class PatientFcmTokenUpdate(BaseModel):
    fcm_token: str = Field(min_length=10, max_length=1024)
    notifications_enabled: bool = Field(default=True)


class PatientFcmPreferencesResponse(BaseModel):
    fcm_token_registered: bool = False
    notifications_enabled: bool = False
    fcm_token_updated_at: str | None = None


# ============================================================
# STAFF CREATION
# ============================================================

class StaffUserCreate(BaseModel):

    email: str = Field(
        min_length=5,
        max_length=254,
    )

    password: str = Field(
        min_length=8,
        max_length=128,
    )

    role: UserRole

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
    )

    department: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
    )

    # Doctor shift / availability settings.
    # These values are ignored for nurse/reception accounts.
    shift_start: str = Field(
    default="00:00",
    pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
)

    shift_end: str = Field(
    default="00:00",
    pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
)

    on_duty: bool = True

    queue_capacity: int = Field(
        default=25,
        ge=1,
        le=1000,
    )


# ============================================================
# LOGIN
# ============================================================

class UserLogin(BaseModel):

    email: str = Field(
        min_length=5,
        max_length=254,
    )

    password: str = Field(
        min_length=8,
        max_length=128,
    )


class GoogleAuthRequest(BaseModel):
    access_token: str = Field(
        min_length=1,
        description="Google OAuth2 access token",
    )


# ============================================================
# USER RESPONSE
# ============================================================

class UserResponse(BaseModel):

    email: str

    role: UserRole

    name: str | None = None

    department: str | None = None

    shift_start: str | None = None

    shift_end: str | None = None

    on_duty: bool | None = None

    queue_capacity: int | None = None

    phone_number: str | None = None
    sms_opt_in: bool = False
    whatsapp_number: str | None = None
    whatsapp_opt_in: bool = False


# ============================================================
# DOCTOR SHIFT UPDATE
# ============================================================

class DoctorShiftUpdate(BaseModel):

    shift_start: str = Field(
        default="09:00",
        pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
    )

    shift_end: str = Field(
        default="17:00",
        pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
    )

    on_duty: bool = True

    queue_capacity: int = Field(
        default=25,
        ge=1,
        le=1000,
    )