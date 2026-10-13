import asyncio
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
import httpx
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from bson import ObjectId

from app.services.ml_client import predict_waiting_time

from app.qr import (
    generate_qr_image_data,
    generate_qr_token,
)

from app.qr_schemas import (
    QRTokenResponse,
    QRVerificationRequest,
    QRVerificationResponse,
)

from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    require_roles,
    verify_password,
)

from app.config import get_settings
from jose import JWTError, jwt
from zoneinfo import ZoneInfo

from app.queue_schemas import (
    NurseAssessmentCreate,
    NurseAssessmentResponse,
    PublicQueueEntryResponse,
    QueueEntryCreate,
    QueueEntryResponse,
    QueueStatus,
    QueueStatusUpdate,
    TriagePriority,
)

from typing import Any
from app.schemas import (
    DoctorShiftUpdate,
    GoogleAuthRequest,
    PatientFcmPreferencesResponse,
    PatientFcmTokenUpdate,
    PatientSmsPreferencesResponse,
    PatientSmsPreferencesUpdate,
    StaffUserCreate,
    UserCreate,
    UserLogin,
    UserResponse,
    UserRole,
)

from app.services.sms_service import normalize_phone_number
from app.services.fcm_service import maybe_send_patient_fcm_notification


# ============================================================
# SETTINGS
# ============================================================

settings = get_settings()


# ============================================================
# NURSE UPDATE REQUEST SCHEMAS
# ============================================================

class NursePriorityUpdate(BaseModel):
    priority: TriagePriority


class NurseDoctorAssignmentUpdate(BaseModel):
    doctor_email: str = Field(min_length=5, max_length=254)


class DoctorConsultationCreate(BaseModel):
    diagnosis: str = Field(default="", max_length=4000)
    consultation_notes: str = Field(default="", max_length=6000)
    prescription: str = Field(default="", max_length=6000)
    treatment_advice: str = Field(default="", max_length=6000)


class DoctorConsultationResponse(BaseModel):
    id: str
    token_number: int
    patient_email: str
    department: str
    doctor_email: str
    diagnosis: str
    consultation_notes: str
    prescription: str
    treatment_advice: str
    started_at: str | None
    completed_at: str | None
    created_at: str
    updated_at: str


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Smart QR-Based Hospital Patient Journey "
        "Management System."
    ),
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# MONGODB
# ============================================================

mongo_client = MongoClient(
    settings.mongodb_uri,
    serverSelectionTimeoutMS=2000,
)

database = mongo_client.get_database()

users_collection = database["users"]

queue_collection = database["queue_entries"]

qr_tokens_collection = database["qr_tokens"]

nurse_assessments_collection = database[
    "nurse_assessments"
]

doctor_consultations_collection = database[
    "doctor_consultations"
]


# ============================================================
# ACTIVE DOCTOR QUEUE STATUSES
# ============================================================

ACTIVE_STATUSES = {
    QueueStatus.WAITING.value,
    QueueStatus.CALLED.value,
    QueueStatus.IN_CONSULTATION.value,
}


# ============================================================
# TRIAGE STATUS
# ============================================================

TRIAGE_STATUS = (
    QueueStatus.WAITING_FOR_TRIAGE.value
)

RECEPTION_STATUS = (
    QueueStatus.WAITING_FOR_RECEPTION.value
)

DOCTOR_CAPACITY_STATUSES = {
    TRIAGE_STATUS,
    RECEPTION_STATUS,
    *ACTIVE_STATUSES,
}

DEFAULT_SHIFT_START = "00:00"
DEFAULT_SHIFT_END = "00:00"
DEFAULT_QUEUE_CAPACITY = 25
HOSPITAL_TIMEZONE = ZoneInfo("Asia/Kolkata")

ADMIN_RECEPTION_DEPENDENCY = require_roles(
    "admin",
    "reception",
)


# ============================================================
# PRIORITY ORDER
#
# Lower number = higher priority
# ============================================================

PRIORITY_ORDER = {
    TriagePriority.URGENT.value: 1,
    TriagePriority.HIGH.value: 2,
    TriagePriority.MEDIUM.value: 3,
    TriagePriority.NORMAL.value: 4,
}


# ============================================================
# DATABASE HEALTH
# ============================================================

@app.get(
    f"{settings.api_prefix}/db-health",
    tags=["system"],
)
def database_health() -> dict[str, str]:

    try:
        mongo_client.admin.command("ping")

        return {
            "status": "ok",
            "database": "MongoDB connected",
        }

    except Exception:

        return {
            "status": "error",
            "database": "MongoDB unavailable",
        }


# ============================================================
# HEALTH
# ============================================================

@app.get(
    f"{settings.api_prefix}/health",
    tags=["system"],
)
async def health_check() -> dict[str, str]:

    return {
        "status": "ok",
        "service": settings.app_name,
        "phase": "5 - Nurse Triage",
    }


# ============================================================
# AUTH - REGISTER PATIENT
# ============================================================

@app.post(
    f"{settings.api_prefix}/auth/register",
    response_model=UserResponse,
    status_code=201,
    tags=["authentication"],
)
def register_patient(
    user: UserCreate,
) -> UserResponse:

    email = user.email.strip().lower()

    existing_user = users_collection.find_one(
        {
            "email": email,
        },
        {
            "_id": 1,
        },
    )

    if existing_user:

        raise HTTPException(
            status_code=409,
            detail=(
                "An account with this email "
                "already exists"
            ),
        )

    raw_phone = user.phone_number or user.whatsapp_number
    clean_phone = normalize_phone_number(raw_phone) if raw_phone else None
    opt_in = bool((user.sms_opt_in or user.whatsapp_opt_in) and clean_phone)

    users_collection.insert_one(
        {
            "email": email,
            "password_hash": hash_password(
                user.password
            ),
            "role": "patient",
            "phone_number": clean_phone,
            "sms_opt_in": opt_in,
            "whatsapp_number": clean_phone,
            "whatsapp_opt_in": opt_in,
        }
    )

    return UserResponse(
        email=email,
        role=UserRole.PATIENT,
        phone_number=clean_phone,
        sms_opt_in=opt_in,
        whatsapp_number=clean_phone,
        whatsapp_opt_in=opt_in,
    )


# ============================================================
# AUTH - LOGIN
# ============================================================

@app.post(
    f"{settings.api_prefix}/auth/login",
    tags=["authentication"],
)
def login_user(
    user: UserLogin,
) -> dict[str, str]:

    email = user.email.strip().lower()

    stored_user = users_collection.find_one(
        {
            "email": email,
        }
    )

    if (
        not stored_user
        or not verify_password(
            user.password,
            stored_user["password_hash"],
        )
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    access_token = create_access_token(
        subject=email,
        role=stored_user["role"],
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": stored_user["role"],
    }


# ============================================================
# AUTH - GOOGLE LOGIN / REGISTER (PATIENTS)
# ============================================================

@app.post(
    f"{settings.api_prefix}/auth/google",
    tags=["authentication"],
)
async def google_auth(
    payload: GoogleAuthRequest,
) -> dict[str, str]:
    access_token = payload.access_token.strip()
    if not access_token:
        raise HTTPException(
            status_code=400,
            detail="Google access token is required.",
        )

    # Validate the access token with Google userinfo API
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid or expired Google access token.",
                )
            userinfo = resp.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail="Unable to verify token with Google servers.",
        ) from e

    email = str(userinfo.get("email") or "").strip().lower()
    email_verified = bool(userinfo.get("email_verified", False))

    if not email or not email_verified:
        raise HTTPException(
            status_code=400,
            detail="Google account email is not verified.",
        )

    # Check if user already exists
    stored_user = users_collection.find_one({"email": email})

    if stored_user:
        # Check role - only patient accounts are permitted through patient Google auth
        if stored_user.get("role") != "patient":
            raise HTTPException(
                status_code=403,
                detail=f"This Google account is associated with a {stored_user.get('role')} account. Please use staff sign-in.",
            )
    else:
        # Create new patient user record
        random_pwd = secrets.token_urlsafe(32)
        patient_doc = {
            "email": email,
            "password_hash": hash_password(random_pwd),
            "role": "patient",
            "name": userinfo.get("name") or "",
            "google_auth": True,
            "created_at": datetime.now(timezone.utc),
        }
        users_collection.insert_one(patient_doc)
        stored_user = patient_doc

    # Generate the EXISTING Care+ JWT using create_access_token()
    jwt_token = create_access_token(
        subject=email,
        role=stored_user["role"],
    )

    return {
        "access_token": jwt_token,
        "token_type": "bearer",
        "role": stored_user["role"],
        "email": email,
    }


# ============================================================
# AUTH - CURRENT USER
# ============================================================

@app.get(
    f"{settings.api_prefix}/auth/me",
    tags=["authentication"],
)
def get_logged_in_user(
    current_user: dict[str, str] = Depends(
        get_current_user
    ),
) -> dict[str, str]:

    return current_user



# ============================================================
# PATIENT AREA
# ============================================================

@app.get(
    f"{settings.api_prefix}/patient-area",
    tags=["authorization"],
)
def patient_area(
    current_user: dict[str, str] = Depends(
        require_roles("patient")
    ),
) -> dict[str, str]:

    return {
        "message": (
            "Patient area accessed successfully"
        ),
        "email": current_user["email"],
        "role": current_user["role"],
    }


# ============================================================
# ADMIN - CREATE STAFF
# ============================================================

@app.post(
    f"{settings.api_prefix}/admin/users",
    response_model=UserResponse,
    status_code=201,
    tags=["administration"],
)
def create_staff_user(
    user: StaffUserCreate,
    current_user: dict[str, str] = Depends(
        require_roles("admin")
    ),
) -> UserResponse:

    email = user.email.strip().lower()

    existing_user = users_collection.find_one(
        {
            "email": email,
        },
        {
            "_id": 1,
        },
    )

    if existing_user:

        raise HTTPException(
            status_code=409,
            detail=(
                "An account with this email "
                "already exists"
            ),
        )

    staff_document: dict[str, object] = {
        "email": email,
        "password_hash": hash_password(
            user.password
        ),
        "role": user.role.value,
    }

    # Doctor accounts need a department so patients can
    # select a valid doctor before joining the queue.
    name = getattr(user, "name", None)
    if isinstance(name, str) and name:
        staff_document["name"] = name.strip()

    department_name = getattr(user, "department", None)
    if department_name is not None:
        staff_document["department"] = department_name.strip()

    if user.role.value == "doctor":
        staff_document["shift_start"] = user.shift_start
        staff_document["shift_end"] = user.shift_end
        staff_document["on_duty"] = user.on_duty
        staff_document["queue_capacity"] = user.queue_capacity

    users_collection.insert_one(staff_document)

    return UserResponse(
        email=email,
        role=user.role,
        name=staff_document.get("name"),
        department=staff_document.get("department"),
        shift_start=staff_document.get("shift_start"),
        shift_end=staff_document.get("shift_end"),
        on_duty=staff_document.get("on_duty"),
        queue_capacity=staff_document.get("queue_capacity"),
    )


# ============================================================
# ADMIN - LIST USERS
#
# Admin can view all registered users.
# Password hashes are NEVER returned.
# ============================================================

@app.get(
    f"{settings.api_prefix}/admin/users",
    response_model=list[UserResponse],
    tags=["administration"],
)
def get_admin_users(
    current_user: dict[str, str] = Depends(
        require_roles("admin")
    ),
) -> list[UserResponse]:

    users = list(
        users_collection.find(
            {},
            {
                "_id": 0,
                "email": 1,
                "role": 1,
                "name": 1,
                "department": 1,
                "shift_start": 1,
                "shift_end": 1,
                "on_duty": 1,
                "queue_capacity": 1,
            },
        )
    )

    return [
        UserResponse(
            email=user["email"],
            role=user["role"],
            name=user.get("name"),
            department=user.get("department"),
            shift_start=user.get("shift_start"),
            shift_end=user.get("shift_end"),
            on_duty=user.get("on_duty"),
            queue_capacity=user.get("queue_capacity"),
        )
        for user in users
    ]


# ============================================================
# ADMIN - UPDATE DOCTOR SHIFT
# ============================================================

@app.patch(
    f"{settings.api_prefix}/admin/doctors/{{doctor_email}}/shift",
    response_model=UserResponse,
    tags=["administration"],
)
def update_doctor_shift(
    doctor_email: str,
    shift_update: DoctorShiftUpdate,
    current_user: dict[str, str] = Depends(
        require_roles("admin")
    ),
) -> UserResponse:

    clean_email = doctor_email.strip().lower()
    doctor = users_collection.find_one({"email": clean_email})

    if not doctor:
        raise HTTPException(
            status_code=404,
            detail="Doctor account not found",
        )

    if doctor.get("role") != "doctor":
        raise HTTPException(
            status_code=400,
            detail="Shift updates can only be applied to doctor accounts",
        )

    update_fields = {
        "shift_start": shift_update.shift_start,
        "shift_end": shift_update.shift_end,
        "on_duty": shift_update.on_duty,
        "queue_capacity": shift_update.queue_capacity,
    }

    users_collection.update_one(
        {"email": clean_email},
        {"$set": update_fields},
    )

    updated_doctor = users_collection.find_one(
        {"email": clean_email},
        {"_id": 0, "password_hash": 0},
    )

    return UserResponse(
        email=updated_doctor["email"],
        role=updated_doctor["role"],
        name=updated_doctor.get("name"),
        department=updated_doctor.get("department"),
        shift_start=updated_doctor.get("shift_start"),
        shift_end=updated_doctor.get("shift_end"),
        on_duty=updated_doctor.get("on_duty"),
        queue_capacity=updated_doctor.get("queue_capacity"),
    )


# ============================================================
# ADMIN - DELETE STAFF / USER
# ============================================================

@app.delete(
    f"{settings.api_prefix}/admin/users/{{user_email}}",
    tags=["administration"],
)
def delete_admin_user(
    user_email: str,
    current_user: dict[str, str] = Depends(
        require_roles("admin")
    ),
) -> dict[str, str]:

    clean_email = user_email.strip().lower()

    if clean_email == current_user["email"].strip().lower():
        raise HTTPException(
            status_code=400,
            detail="Administrators cannot delete their own active account",
        )

    target_user = users_collection.find_one({"email": clean_email})

    if not target_user:
        raise HTTPException(
            status_code=404,
            detail="User account not found",
        )

    # Delete the user document
    users_collection.delete_one({"email": clean_email})

    return {
        "message": f"User {clean_email} has been successfully removed",
        "email": clean_email,
    }



# ============================================================
# ADMIN - VIEW ALL QUEUES
#
# READ ONLY
#
# Admin can monitor queue information across
# all departments but cannot modify queue state.
# ============================================================

@app.get(
    f"{settings.api_prefix}/admin/queue",
    response_model=list[QueueEntryResponse],
    tags=["administration"],
)
def get_admin_queue(
    current_user: dict[str, str] = Depends(
        require_roles("admin")
    ),
) -> list[QueueEntryResponse]:

    entries = list(
        queue_collection.find(
            {},
            {
                "_id": 0,
            },
        )
    )

    # --------------------------------------------------------
    # Sort:
    # 1. Department
    # 2. Active patients first
    # 3. Priority
    # 4. Position
    # 5. Token number
    # --------------------------------------------------------

    entries.sort(
        key=lambda entry: (

            entry.get(
                "department",
                "",
            ),

            0
            if entry.get("status")
            in ACTIVE_STATUSES
            else 1,

            get_priority_rank(
                entry
            )
            if entry.get("status")
            in ACTIVE_STATUSES
            else 999,

            (
                entry.get(
                    "position",
                    999999,
                )
                if entry.get(
                    "position",
                    0,
                ) > 0
                else 999999
            ),

            entry.get(
                "token_number",
                999999,
            ),
        )
    )

    return [
        queue_response(entry)
        for entry in entries
    ]


# ============================================================
# BUILD ML INPUT
# ============================================================

async def build_ml_prediction(
    *,
    department: str,
    doctor_email: str | None,
    position: int,
    queue_length: int,
    priority: str = TriagePriority.NORMAL.value,
) -> dict[str, Any]:

    now = datetime.now()

    if queue_length <= 5:
        queue_congestion = 0.20

    elif queue_length <= 10:
        queue_congestion = 0.45

    elif queue_length <= 20:
        queue_congestion = 0.70

    else:
        queue_congestion = 0.90

    normalized_priority = (
        str(priority)
        .strip()
        .lower()
    )

    if normalized_priority not in PRIORITY_ORDER:

        normalized_priority = (
            TriagePriority.NORMAL.value
        )

    ml_input = {

        "time_step": 0,

        "queue_congestion":
            queue_congestion,

        "patients_ahead":
            max(position - 1, 0),

        "queue_length":
            queue_length,

        "doctor_available":
            1,

        "doctor_delay_minutes":
            0,

        "average_consultation_minutes":
            15,

        "completed_patients":
            0,

        "historical_average_wait":
            30,

        "historical_queue_length":
            10,

        "arrival_hour":
            now.hour,

        "no_show_probability":
            0.10,

        "doctor_id":
            doctor_email or "UNKNOWN",

        "department":
            department,

        "patient_type":
            "Regular",

        "priority_level":
            normalized_priority.title(),

        "appointment_type":
            "Walk-in",

        "day_of_week":
            now.strftime("%A"),
    }

    return await predict_waiting_time(
        ml_input
    )


# ============================================================
# STORE ML PREDICTION
# ============================================================

def prediction_fields(
    prediction: dict[str, Any],
) -> dict[str, Any]:

    return {

        "predicted_wait_minutes":
            prediction[
                "predicted_wait_minutes"
            ],

        "probability_short":
            prediction[
                "probability_short"
            ],

        "probability_moderate":
            prediction[
                "probability_moderate"
            ],

        "probability_long":
            prediction[
                "probability_long"
            ],

        "probability_very_long":
            prediction[
                "probability_very_long"
            ],

        "probability_long_or_more":
            prediction[
                "probability_long_or_more"
            ],

        "bayesian_state":
            prediction[
                "bayesian_state"
            ],

        "bayesian_expected_wait_minutes":
            prediction[
                "bayesian_expected_wait_minutes"
            ],

        "risk_level":
            prediction[
                "risk_level"
            ],
    }


# ============================================================
# CLEAR ML PREDICTION
# ============================================================

def clear_prediction_fields() -> dict[str, Any]:

    return {

        "predicted_wait_minutes": None,

        "probability_short": None,

        "probability_moderate": None,

        "probability_long": None,

        "probability_very_long": None,

        "probability_long_or_more": None,

        "bayesian_state": None,

        "bayesian_expected_wait_minutes": None,

        "risk_level": None,
    }


# ============================================================
# PRIORITY RANK
# ============================================================

def get_priority_rank(
    entry: dict[str, Any],
) -> int:

    priority = (
        entry.get(
            "priority",
            TriagePriority.NORMAL.value,
        )
        or TriagePriority.NORMAL.value
    )

    priority = (
        str(priority)
        .strip()
        .lower()
    )

    return PRIORITY_ORDER.get(
        priority,
        PRIORITY_ORDER[
            TriagePriority.NORMAL.value
        ],
    )


# ============================================================
# REBUILD DOCTOR QUEUE
# ============================================================

async def recalculate_queue_state(
    department: str,
) -> None:

    department = department.strip()

    active_entries = list(
        queue_collection.find(
            {
                "department":
                    department,

                "status": {
                    "$in":
                        list(
                            ACTIVE_STATUSES
                        )
                },
            }
        )
    )

    # --------------------------------------------------------
    # Group active entries by assigned doctor
    # (Each doctor has their own queue, so positions start at 1 per doctor)
    # --------------------------------------------------------
    doctor_groups: dict[str, list[dict]] = {}
    for entry in active_entries:
        doc_email = (entry.get("doctor_email") or "").strip().lower()
        doctor_groups.setdefault(doc_email, []).append(entry)

    for doc_email, doc_entries in doctor_groups.items():
        doc_entries.sort(
            key=lambda entry: (
                get_priority_rank(
                    entry
                ),
                (
                    entry.get(
                        "position",
                        999999,
                    )
                    if isinstance(
                        entry.get(
                            "position"
                        ),
                        int,
                    )
                    and entry.get(
                        "position",
                        0,
                    ) > 0
                    else 999999
                ),
                entry.get(
                    "token_number",
                    999999,
                ),
            )
        )

        # ----------------------------------------------------
        # Assign positions per doctor queue
        # ----------------------------------------------------
        for index, entry in enumerate(
            doc_entries,
            start=1,
        ):
            queue_collection.update_one(
                {
                    "_id":
                        entry["_id"]
                },
                {
                    "$set": {
                        "position":
                            index,
                        "updated_at":
                            datetime.now(
                                timezone.utc
                            ),
                    }
                },
            )

        doc_queue_length = len(doc_entries)

        # ----------------------------------------------------
        # ML prediction only for waiting patients
        # ----------------------------------------------------
        for index, entry in enumerate(
            doc_entries,
            start=1,
        ):
            if (
                entry["status"]
                != QueueStatus.WAITING.value
            ):
                continue

            try:
                prediction = (
                    await build_ml_prediction(
                        department=
                            department,
                        doctor_email=
                            entry.get(
                                "doctor_email"
                            ),
                        position=
                            index,
                        queue_length=
                            doc_queue_length,
                        priority=
                            entry.get(
                                "priority",
                                TriagePriority.NORMAL.value,
                            ),
                    )
                )

                queue_collection.update_one(
                    {
                        "_id":
                            entry["_id"]
                    },
                    {
                        "$set": {
                            **prediction_fields(
                                prediction
                            ),
                            "updated_at":
                                datetime.now(
                                    timezone.utc
                                ),
                        }
                    },
                )
            except Exception as error:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "ML prediction service unavailable: "
                        f"{error}"
                    ),
                )

        # ----------------------------------------------------
        # SMS notifications for active waiting patients
        # Non-blocking, isolated check with duplicate protection
        # ----------------------------------------------------
        for index, entry in enumerate(
            doc_entries,
            start=1,
        ):
            if entry["status"] != QueueStatus.WAITING.value:
                continue
            try:
                fresh_entry = queue_collection.find_one({"_id": entry["_id"]})
                if fresh_entry:
                    asyncio.create_task(
                        maybe_send_sms_queue_notification(
                            fresh_entry,
                            users_collection,
                            queue_collection,
                            force_position=index,
                        )
                    )
                    asyncio.create_task(
                        maybe_send_patient_fcm_notification(
                            fresh_entry,
                            users_collection,
                            force_position=index,
                        )
                    )
            except Exception:
                pass

    # --------------------------------------------------------
    # Skipped patients position = 0
    # --------------------------------------------------------
    queue_collection.update_many(
        {
            "department":
                department,
            "status":
                QueueStatus.SKIPPED.value,
        },
        {
            "$set": {
                "position": 0,
                "updated_at":
                    datetime.now(
                        timezone.utc
                    ),
            }
        },
    )


# ============================================================
# PRIVATE QUEUE RESPONSE
# ============================================================

def queue_response(
    entry: dict,
) -> QueueEntryResponse:

    return QueueEntryResponse(

        token_number=
            entry["token_number"],

        patient_email=
            entry["patient_email"],

        department=
            entry["department"],

        doctor_email=
            entry.get(
                "doctor_email"
            ),

        status=
            QueueStatus(
                entry["status"]
            ),

        position=
            entry.get(
                "position",
                0,
            ),

        priority=
            TriagePriority(
                entry.get(
                    "priority",
                    TriagePriority.NORMAL.value,
                )
            ),

        predicted_wait_minutes=
            entry.get(
                "predicted_wait_minutes"
            ),

        probability_short=
            entry.get(
                "probability_short"
            ),

        probability_moderate=
            entry.get(
                "probability_moderate"
            ),

        probability_long=
            entry.get(
                "probability_long"
            ),

        probability_very_long=
            entry.get(
                "probability_very_long"
            ),

        probability_long_or_more=
            entry.get(
                "probability_long_or_more"
            ),

        bayesian_state=
            entry.get(
                "bayesian_state"
            ),

        bayesian_expected_wait_minutes=
            entry.get(
                "bayesian_expected_wait_minutes"
            ),

        risk_level=
            entry.get(
                "risk_level"
            ),

        queue_access_verified=bool(
            entry.get(
                "queue_access_verified",
                False,
            )
        ),
    )


# ============================================================
# DOCTOR SHIFT / CAPACITY HELPERS
# ============================================================

def _doctor_schedule(doctor: dict[str, Any]) -> tuple[str, str, bool, int]:
    return (
        str(doctor.get("shift_start") or DEFAULT_SHIFT_START),
        str(doctor.get("shift_end") or DEFAULT_SHIFT_END),
        bool(doctor.get("on_duty", True)),
        int(doctor.get("queue_capacity") or DEFAULT_QUEUE_CAPACITY),
    )


def _time_to_minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def _doctor_shift_state(doctor: dict[str, Any]) -> tuple[bool, str]:
    shift_start, shift_end, on_duty, _ = _doctor_schedule(doctor)

    if not on_duty:
        return False, "Doctor is currently not on duty."

    now = datetime.now(HOSPITAL_TIMEZONE)
    current_minutes = now.hour * 60 + now.minute
    start_minutes = _time_to_minutes(shift_start)
    end_minutes = _time_to_minutes(shift_end)

    if start_minutes == end_minutes:
        return True, ""

    if start_minutes < end_minutes:
        if current_minutes < start_minutes:
            return False, "Doctor shift has not started yet."
        if current_minutes >= end_minutes:
            return False, "Doctor shift is over."
    else:
        # Overnight shift, e.g. 22:00 - 06:00.
        if current_minutes >= end_minutes and current_minutes < start_minutes:
            return False, "Doctor is outside the current shift."

    return True, ""


def get_doctor_availability(doctor: dict[str, Any]) -> dict[str, Any]:
    email = (doctor.get("email") or "").strip().lower()
    shift_start, shift_end, on_duty, capacity = _doctor_schedule(doctor)
    active_count = queue_collection.count_documents(
        {
            "doctor_email": email,
            "status": {"$in": list(DOCTOR_CAPACITY_STATUSES)},
        }
    )

    in_shift, reason = _doctor_shift_state(doctor)

    if not in_shift:
        availability = "unavailable"
    elif active_count > capacity:
        availability = "busy"
        reason = "Doctor queue capacity has been exceeded."
    else:
        availability = "available"
        reason = ""

    return {
        "email": email,
        "name": doctor.get("name") or email,
        "department": doctor.get("department"),
        "availability": availability,
        "available": availability == "available",
        "availability_reason": reason,
        "queue_count": active_count,
        "queue_capacity": capacity,
        "shift_start": shift_start,
        "shift_end": shift_end,
        "on_duty": on_duty,
    }


# ============================================================
# PATIENT - AVAILABLE DOCTORS BY DEPARTMENT
#
# Returns doctors assigned to the selected department and marks
# a doctor unavailable when they already have an active queue
# patient.
# ============================================================

@app.get(
    f"{settings.api_prefix}/doctors/{{department}}",
    tags=["patient"],
)
def get_available_doctors(
    department: str,
    current_user: dict[str, str] = Depends(
        require_roles("patient")
    ),
) -> list[dict[str, Any]]:

    department = department.strip()

    if not department:
        raise HTTPException(
            status_code=400,
            detail="Department is required",
        )

    if department.lower() in ["general", "general medicine"]:
        dept_match = {"$in": ["General", "General Medicine", None]}
    else:
        dept_match = department

    doctors = list(
        users_collection.find(
            {
                "role": "doctor",
                "department": dept_match,
            },
            {
                "_id": 0,
                "email": 1,
                "name": 1,
                "department": 1,
                "shift_start": 1,
                "shift_end": 1,
                "on_duty": 1,
                "queue_capacity": 1,
            },
        )
    )

    result = [
        get_doctor_availability(doctor)
        for doctor in doctors
        if (doctor.get("email") or "").strip()
    ]

    availability_order = {
        "available": 0,
        "busy": 1,
        "unavailable": 2,
    }

    result.sort(
        key=lambda doctor: (
            availability_order.get(doctor["availability"], 9),
            doctor["name"].lower(),
        )
    )

    return result


# ============================================================
# JOIN QUEUE
#
# IMPORTANT:
# Patient does NOT enter doctor queue immediately.
# First goes to nurse triage.
# ============================================================

@app.post(
    f"{settings.api_prefix}/queue",
    response_model=QueueEntryResponse,
    status_code=201,
    tags=["queue"],
)
async def create_queue_entry(
    entry: QueueEntryCreate,
    current_user: dict[str, str] = Depends(
        require_roles(
            "patient",
            "reception",
        )
    ),
) -> QueueEntryResponse:

    patient_email = (

        current_user["email"]

        if current_user["role"]
        == "patient"

        else (entry.patient_email or "")
        .strip()
        .lower()
    )

    department = (entry.department or "").strip()

    doctor_email = (entry.doctor_email or "").strip().lower()

    # --------------------------------------------------------
    # Validate that the selected doctor really exists, is a
    # doctor account, and belongs to the selected department.
    # --------------------------------------------------------
    if department.lower() in ["general", "general medicine"]:
        doc_dept_match = {"$in": ["General", "General Medicine", None]}
    else:
        doc_dept_match = department

    doctor = users_collection.find_one(
        {
            "email": doctor_email,
            "role": "doctor",
            "department": doc_dept_match,
        },
        {"_id": 1},
    )

    if not doctor:
        raise HTTPException(
            status_code=400,
            detail=(
                "Selected doctor is invalid for this department"
            ),
        )

    doctor = users_collection.find_one(
        {
            "email": doctor_email,
            "role": "doctor",
        }
    ) or doctor

    doctor_state = get_doctor_availability(doctor)

    if doctor_state["availability"] == "unavailable":
        raise HTTPException(
            status_code=409,
            detail=doctor_state["availability_reason"]
            or "Doctor is currently unavailable.",
        )

    if doctor_state["availability"] == "busy":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Dr. {doctor_state['name']} has reached the queue capacity "
                f"of {doctor_state['queue_capacity']} patients."
            ),
        )

    # --------------------------------------------------------
    # Check whether patient already has an active entry
    # --------------------------------------------------------

    existing_entry = (
        queue_collection.find_one(
            {
                "patient_email":
                    patient_email,

                "status": {
                    "$in": [
                        TRIAGE_STATUS,
                        *ACTIVE_STATUSES,
                    ]
                },
            }
        )
    )

    if existing_entry:

        raise HTTPException(
            status_code=409,
            detail=(
                "Patient already has an active "
                "queue entry"
            ),
        )

    # --------------------------------------------------------
    # Nurse waiting position
    # --------------------------------------------------------

    triage_count = (
        queue_collection.count_documents(
            {
                "department":
                    department,

                "status":
                    TRIAGE_STATUS,
            }
        )
    )

    # --------------------------------------------------------
    # Generate token
    # --------------------------------------------------------

    last_entry = (
        queue_collection.find_one(
            {
                "department":
                    department
            },
            sort=[
                ("token_number", -1)
            ],
        )
    )

    next_token = (

        (
            last_entry.get(
                "token_number",
                0,
            )
            + 1
        )

        if last_entry

        else 1
    )

    queue_document = {

        "token_number":
            next_token,

        "patient_email":
            patient_email,

        "department":
            department,

        "doctor_email":
            doctor_email,

        "status":
            TRIAGE_STATUS,

        "position":
            triage_count + 1,

        "priority":
            TriagePriority.NORMAL.value,

        # Patient cannot access the live doctor queue until
        # reception verifies the official QR for this queue.
        "queue_access_verified": False,

        "created_at":
            datetime.now(
                timezone.utc
            ),

        "updated_at":
            datetime.now(
                timezone.utc
            ),
    }

    result = (
        queue_collection.insert_one(
            queue_document
        )
    )

    created = queue_collection.find_one(
        {
            "_id":
                result.inserted_id
        }
    )

    if not created:

        raise HTTPException(
            status_code=500,
            detail=(
                "Queue entry was not created"
            ),
        )

    try:
        asyncio.create_task(
            maybe_send_sms_queue_notification(
                created,
                users_collection,
                queue_collection,
                force_status=QueueStatus.WAITING_FOR_TRIAGE.value,
            )
        )
        asyncio.create_task(
            maybe_send_patient_fcm_notification(
                created,
                users_collection,
                force_status=QueueStatus.WAITING_FOR_TRIAGE.value,
            )
        )
    except Exception:
        pass

    return queue_response(
        created
    )


# ============================================================
# GET MY QUEUE
# ============================================================

@app.get(
    f"{settings.api_prefix}/queue/my",
    response_model=QueueEntryResponse | None,
    tags=["queue"],
)
def get_my_queue_entry(
    current_user: dict[str, str] = Depends(
        require_roles("patient")
    ),
) -> QueueEntryResponse | None:

    queue_entry = queue_collection.find_one(
        {
            "patient_email":
                current_user["email"],

            "status": {
                "$in": [
                    TRIAGE_STATUS,
                    RECEPTION_STATUS,
                    *ACTIVE_STATUSES,
                    QueueStatus.SKIPPED.value,
                ]
            },
        },
        sort=[
            ("_id", -1)
        ],
    )

    # A patient without an active queue is a normal state.
    # Return HTTP 200 with JSON null instead of HTTP 404.
    # This prevents the patient dashboard's polling loop from
    # filling the browser console with expected 404 errors.
    if not queue_entry:
        return None

    return queue_response(
        queue_entry
    )

# ============================================================
# DOCTOR ACCESS CONTROL
# ============================================================

def ensure_doctor_department_access(
    department: str,
    current_user: dict[str, str],
) -> None:
    if current_user["role"] != "doctor":
        return

    doctor_email = current_user["email"].strip().lower()
    department = department.strip()

    if not queue_collection.find_one(
        {"department": department, "doctor_email": doctor_email},
        {"_id": 1},
    ):
        raise HTTPException(
            status_code=403,
            detail="Doctor does not have access to this department",
        )


def ensure_doctor_queue_entry_access(
    queue_entry: dict[str, Any],
    current_user: dict[str, str],
) -> None:
    if current_user["role"] != "doctor":
        return

    doctor_email = current_user["email"].strip().lower()
    assigned_doctor = (queue_entry.get("doctor_email") or "").strip().lower()

    if assigned_doctor != doctor_email:
        raise HTTPException(
            status_code=403,
            detail="Doctor does not have access to this patient",
        )


def ensure_doctor_assessment_access(
    assessment: dict[str, Any],
    current_user: dict[str, str],
) -> None:
    if current_user["role"] != "doctor":
        return

    doctor_email = current_user["email"].strip().lower()
    assigned_doctor = (assessment.get("doctor_email") or "").strip().lower()

    if assigned_doctor != doctor_email:
        raise HTTPException(
            status_code=403,
            detail="Doctor does not have access to this patient assessment",
        )


def validate_doctor_status_transition(
    current_status: str,
    new_status: str,
) -> None:
    allowed_transitions = {
        QueueStatus.WAITING.value: {
            QueueStatus.CALLED.value,
            QueueStatus.IN_CONSULTATION.value,
        },
        QueueStatus.CALLED.value: {QueueStatus.IN_CONSULTATION.value},
        QueueStatus.IN_CONSULTATION.value: {QueueStatus.COMPLETED.value},
        QueueStatus.COMPLETED.value: set(),
        QueueStatus.SKIPPED.value: set(),
        TRIAGE_STATUS: set(),
    }

    if new_status not in allowed_transitions.get(current_status, set()):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid doctor status transition: "
                f"{current_status} -> {new_status}"
            ),
        )


# ============================================================
# FULL DEPARTMENT QUEUE
#
# Doctor / Reception
# ============================================================

@app.get(
    f"{settings.api_prefix}/queue/{{department}}",
    response_model=list[
        QueueEntryResponse
    ],
    tags=["queue"],
)
def get_department_queue(
    department: str,
    current_user: dict[str, str] = Depends(
        require_roles(
            "doctor",
            "reception",
        )
    ),
) -> list[QueueEntryResponse]:

    department = department.strip()

    ensure_doctor_department_access(
        department,
        current_user,
    )

    queue_filter: dict[str, Any] = {
        "department": department,
        "status": {
            "$in": [
                QueueStatus.WAITING_FOR_RECEPTION.value,
                QueueStatus.WAITING.value,
                QueueStatus.CALLED.value,
                QueueStatus.IN_CONSULTATION.value,
                QueueStatus.SKIPPED.value,
            ]
        },
    }

    if current_user["role"] == "doctor":
        queue_filter["doctor_email"] = current_user["email"].strip().lower()

    entries = list(queue_collection.find(queue_filter))

    entries.sort(
        key=lambda entry: (

            0
            if entry["status"]
            in ACTIVE_STATUSES
            else 1,

            get_priority_rank(
                entry
            )
            if entry["status"]
            in ACTIVE_STATUSES
            else 999,

            (
                entry.get(
                    "position",
                    999999,
                )
                if entry.get(
                    "position",
                    0,
                ) > 0
                else 999999
            ),

            entry.get(
                "token_number",
                999999,
            ),
        )
    )

    return [
        queue_response(
            entry
        )
        for entry in entries
    ]


# ============================================================
# DOCTOR - GET OWN PATIENT
# ============================================================

@app.get(
    f"{settings.api_prefix}/doctor/patients/{{token_number}}",
    response_model=QueueEntryResponse | None,
    tags=["doctor"],
)
def get_doctor_patient(
    token_number: int,
    current_user: dict[str, str] = Depends(
        require_roles("doctor")
    ),
) -> QueueEntryResponse | None:
    doctor_email = current_user["email"].strip().lower()

    queue_entry = queue_collection.find_one(
        {
            "doctor_email": doctor_email,
            "token_number": token_number,
        },
        sort=[("_id", -1)],
    )

    if not queue_entry:
        return None

    return queue_response(queue_entry)


# ============================================================
# PUBLIC DEPARTMENT QUEUE
#
# Patients see token/status/position only.
# No patient email.
# No doctor email.
# ============================================================

@app.get(
    f"{settings.api_prefix}/queue/{{department}}/public",
    response_model=list[
        PublicQueueEntryResponse
    ],
    tags=["queue"],
)
def get_public_department_queue(
    department: str,
    current_user: dict[str, str] = Depends(
        require_roles("patient")
    ),
) -> list[PublicQueueEntryResponse]:

    department = department.strip()

    entries = list(
        queue_collection.find(
            {
                "department":
                    department,

                "status": {
                    "$in": [
                        QueueStatus.WAITING.value,
                        QueueStatus.CALLED.value,
                        QueueStatus.IN_CONSULTATION.value,
                    ]
                },
            },
            {
                "_id": 0,

                "token_number": 1,

                "department": 1,

                "status": 1,

                "position": 1,
            },
        )
    )

    entries.sort(
        key=lambda entry: (
            entry.get(
                "position",
                999999,
            ),

            entry.get(
                "token_number",
                999999,
            ),
        )
    )

    return [
        PublicQueueEntryResponse(

            token_number=
                entry[
                    "token_number"
                ],

            department=
                entry[
                    "department"
                ],

            status=
                QueueStatus(
                    entry["status"]
                ),

            position=
                entry.get(
                    "position",
                    0,
                ),
        )

        for entry in entries
    ]


@app.get(
    f"{settings.api_prefix}/queue/{{department}}/public/doctor/{{doctor_email}}",
    response_model=list[
        PublicQueueEntryResponse
    ],
    tags=["queue"],
)
def get_public_doctor_queue(
    department: str,
    doctor_email: str,
    current_user: dict[str, str] = Depends(
        require_roles("patient")
    ),
) -> list[PublicQueueEntryResponse]:

    department = department.strip()
    doctor_email = doctor_email.strip().lower()

    entries = list(
        queue_collection.find(
            {
                "department": department,
                "doctor_email": doctor_email,
                "status": {
                    "$in": [
                        QueueStatus.WAITING.value,
                        QueueStatus.CALLED.value,
                        QueueStatus.IN_CONSULTATION.value,
                    ]
                },
            },
            {
                "_id": 0,
                "token_number": 1,
                "department": 1,
                "status": 1,
                "position": 1,
            },
        )
    )

    entries.sort(
        key=lambda entry: (
            entry.get("position", 999999),
            entry.get("token_number", 999999),
        )
    )

    return [
        PublicQueueEntryResponse(
            token_number=entry["token_number"],
            department=entry["department"],
            status=QueueStatus(entry["status"]),
            position=entry.get("position", 0),
        )
        for entry in entries
    ]


# ============================================================
# DOCTOR - DASHBOARD
# ============================================================

@app.get(
    f"{settings.api_prefix}/doctor/dashboard",
    tags=["doctor"],
)
def get_doctor_dashboard(
    current_user: dict[str, str] = Depends(
        require_roles("doctor")
    ),
) -> dict[str, Any]:
    doctor_email = current_user["email"].strip().lower()

    active_entries = list(
        queue_collection.find(
            {
                "doctor_email": doctor_email,
                "$or": [
                    {
                        "status": {
                            "$in": [
                                QueueStatus.CALLED.value,
                                QueueStatus.IN_CONSULTATION.value,
                            ]
                        }
                    },
                    {
                        "status": QueueStatus.WAITING.value,
                        "queue_access_verified": True,
                    },
                ],
            },
            {"_id": 0},
        )
    )

    active_entries.sort(
        key=lambda entry: (
            get_priority_rank(entry),
            entry.get("position", 999999)
            if entry.get("position", 0) > 0
            else 999999,
            entry.get("token_number", 999999),
        )
    )

    departments = sorted({
        entry["department"]
        for entry in active_entries
        if entry.get("department")
    })

    skipped_entries = list(
        queue_collection.find(
            {
                "doctor_email": doctor_email,
                "status": QueueStatus.SKIPPED.value,
            },
            {"_id": 0},
        ).sort("updated_at", -1)
    )

    def _format_doctor_entry(entry: dict[str, Any]) -> dict[str, Any]:
        resp_dict = queue_response(entry).model_dump()
        resp_dict["has_past_records"] = patient_has_past_records(entry.get("patient_email"))
        return resp_dict

    formatted_active = [_format_doctor_entry(entry) for entry in active_entries]
    formatted_skipped = [_format_doctor_entry(entry) for entry in skipped_entries]

    return {
        "doctor_email": doctor_email,
        "departments": departments,
        "active_patient_count": len(active_entries),
        "patients": formatted_active,
        "active_patients": formatted_active,
        "skipped_patients": formatted_skipped,
    }


# ============================================================
# RECEPTION - QUEUE WAITING FOR QR GENERATION
# ============================================================

@app.get(
    f"{settings.api_prefix}/reception/queue/{{department}}",
    response_model=list[QueueEntryResponse],
    tags=["reception"],
)
def get_reception_queue(
    department: str,
    current_user: dict[str, str] = Depends(
        require_roles("reception")
    ),
) -> list[QueueEntryResponse]:

    department = department.strip()

    filter_query: dict[str, Any] = {
        "status": {
            "$in": [
                QueueStatus.WAITING_FOR_RECEPTION.value,
                QueueStatus.WAITING.value,
                QueueStatus.CALLED.value,
                QueueStatus.IN_CONSULTATION.value,
            ]
        }
    }

    if department.lower() != "all":
        if department.lower() in ["general", "general medicine"]:
            filter_query["department"] = {"$in": ["General", "General Medicine"]}
        else:
            filter_query["department"] = department

    entries = list(
        queue_collection.find(
            filter_query,
            {"_id": 0},
        )
    )

    entries.sort(
        key=lambda entry: (
            0
            if (
                entry.get("status") == QueueStatus.WAITING.value
                and not entry.get("queue_access_verified", False)
            )
            else 1,
            get_priority_rank(entry),
            entry.get("position", 999999)
            if entry.get("position", 0) > 0
            else 999999,
            entry.get("token_number", 999999),
        )
    )

    return [queue_response(entry) for entry in entries]


# ============================================================
# NURSE HELPERS
# ============================================================

def get_latest_patient_queue_entry(
    patient_email: str,
    department: str | None = None,
) -> dict[str, Any]:

    query: dict[str, Any] = {
        "patient_email": patient_email.strip().lower(),
    }

    if department:
        query["department"] = department.strip()

    entry = queue_collection.find_one(
        query,
        sort=[("_id", -1)],
    )

    if not entry:
        raise HTTPException(
            status_code=404,
            detail="Queue entry not found for this patient",
        )

    return entry


def ensure_doctor_account(
    doctor_email: str,
    department: str | None = None,
) -> str:

    normalized_email = (
        doctor_email.strip().lower()
    )

    query: dict[str, Any] = {
        "email": normalized_email,
        "role": "doctor",
    }

    if department:
        dept_clean = department.strip()
        if dept_clean.lower() in ["general", "general medicine"]:
            query["department"] = {"$in": ["General", "General Medicine", None]}
        else:
            query["department"] = dept_clean

    doctor = users_collection.find_one(
        query,
        {
            "_id": 1,
        },
    )

    if not doctor:
        raise HTTPException(
            status_code=404,
            detail="Doctor account not found",
        )

    return normalized_email


# ============================================================
# NURSE - GET PATIENTS WAITING FOR TRIAGE
# ============================================================

@app.get(
    f"{settings.api_prefix}/nurse/patients",
    tags=["nurse"],
)
def get_nurse_patients(
    current_user: dict[str, str] = Depends(
        require_roles("nurse")
    ),
) -> list[dict[str, Any]]:

    entries = list(
        queue_collection.find(
            {
                "status":
                    TRIAGE_STATUS,
            },
            {
                "_id": 0,

                "token_number": 1,

                "patient_email": 1,

                "department": 1,

                "doctor_email": 1,

                "status": 1,

                "position": 1,

                "priority": 1,

                "created_at": 1,
            },
        )
    )

    # --------------------------------------------------------
    # Oldest triage patient first
    # --------------------------------------------------------

    entries.sort(
        key=lambda item: (
            item.get(
                "position",
                999999,
            ),

            item.get(
                "token_number",
                999999,
            ),
        )
    )

    for item in entries:
        item["has_past_records"] = patient_has_past_records(item.get("patient_email"))

    return entries


# ============================================================
# NURSE - CREATE ASSESSMENT
#
# waiting_for_triage
#        ↓
# waiting
# ============================================================

@app.post(
    f"{settings.api_prefix}/nurse/assessments",
    response_model=NurseAssessmentResponse,
    status_code=201,
    tags=["nurse"],
)
async def create_nurse_assessment(
    assessment: NurseAssessmentCreate,
    current_user: dict[str, str] = Depends(
        require_roles("nurse")
    ),
) -> NurseAssessmentResponse:

    patient_email = (
        assessment.patient_email
        .strip()
        .lower()
    )

    department = (
        assessment.department
        .strip()
    )

    doctor_email = (
        assessment.doctor_email
        .strip()
        .lower()
        if assessment.doctor_email
        else None
    )

    now = datetime.now(
        timezone.utc
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Find patient specifically in triage.
    # --------------------------------------------------------

    queue_entry = queue_collection.find_one(
        {
            "patient_email":
                patient_email,

            "department":
                department,

            "status":
                TRIAGE_STATUS,
        },
        sort=[
            ("_id", -1)
        ],
    )

    if not queue_entry:

        raise HTTPException(
            status_code=404,
            detail=(
                "Patient is not waiting "
                "for nurse assessment"
            ),
        )

    if doctor_email:
        ensure_doctor_account(
            doctor_email,
            department,
        )

    # --------------------------------------------------------
    # Create nurse assessment
    # --------------------------------------------------------

    document = {

        "patient_email":
            patient_email,

        "department":
            department,

        "doctor_email":
            doctor_email,

        "temperature":
            assessment.temperature,

        "pulse":
            assessment.pulse,

        "systolic_bp":
            assessment.systolic_bp,

        "diastolic_bp":
            assessment.diastolic_bp,

        "spo2":
            assessment.spo2,

        "pain_level":
            assessment.pain_level,

        "symptoms":
            assessment.symptoms,

        "nurse_notes":
            assessment.nurse_notes,

        "priority":
            assessment.priority.value,

        "nurse_email":
            current_user["email"],

        "created_at":
            now,

        "updated_at":
            now,
    }

    result = (
        nurse_assessments_collection.insert_one(
            document
        )
    )

    # --------------------------------------------------------
    # Move patient into doctor queue
    # --------------------------------------------------------

    queue_update = {

        # Nurse triage is complete, but the patient enters the
        # doctor queue only after the patient scans the QR shown
        # by reception.
        "status":
            QueueStatus.WAITING_FOR_RECEPTION.value,

        "priority":
            assessment.priority.value,

        "position":
            0,

        "updated_at":
            now,
    }

    if doctor_email:

        queue_update[
            "doctor_email"
        ] = doctor_email

    queue_collection.update_one(
        {
            "_id":
                queue_entry["_id"]
        },
        {
            "$set":
                queue_update
        },
    )

    # --------------------------------------------------------
    # Do NOT recalculate the doctor queue here.
    # The patient enters the doctor queue only after scanning
    # the QR displayed by reception.
    # --------------------------------------------------------
    try:
        updated_entry = queue_collection.find_one({"_id": queue_entry["_id"]})
        if updated_entry:
            asyncio.create_task(
                maybe_send_sms_queue_notification(
                    updated_entry,
                    users_collection,
                    queue_collection,
                    force_status=QueueStatus.WAITING_FOR_RECEPTION.value,
                )
            )
            asyncio.create_task(
                maybe_send_patient_fcm_notification(
                    updated_entry,
                    users_collection,
                    force_status=QueueStatus.WAITING_FOR_RECEPTION.value,
                )
            )
    except Exception:
        pass

    # --------------------------------------------------------
    # Get updated assessment
    # --------------------------------------------------------

    created_assessment = (
        nurse_assessments_collection.find_one(
            {
                "_id":
                    result.inserted_id
            }
        )
    )

    return NurseAssessmentResponse(

        id=
            str(
                result.inserted_id
            ),

        patient_email=
            patient_email,

        department=
            department,

        doctor_email=
            doctor_email,

        temperature=
            assessment.temperature,

        pulse=
            assessment.pulse,

        systolic_bp=
            assessment.systolic_bp,

        diastolic_bp=
            assessment.diastolic_bp,

        spo2=
            assessment.spo2,

        pain_level=
            assessment.pain_level,

        symptoms=
            assessment.symptoms,

        nurse_notes=
            assessment.nurse_notes,

        priority=
            assessment.priority,

        created_at=
            now.isoformat(),

        updated_at=
            now.isoformat(),
    )


# ============================================================
# NURSE - UPDATE TRIAGE PRIORITY
#
# normal / medium / high / urgent
# Updates both the assessment and the queue.
# The doctor queue is recalculated immediately.
# ============================================================

@app.patch(
    f"{settings.api_prefix}/nurse/assessments/{{patient_email}}/priority",
    response_model=NurseAssessmentResponse,
    tags=["nurse"],
)
async def update_nurse_priority(
    patient_email: str,
    update: NursePriorityUpdate,
    current_user: dict[str, str] = Depends(
        require_roles("nurse")
    ),
) -> NurseAssessmentResponse:

    patient_email = (
        patient_email.strip().lower()
    )

    document = nurse_assessments_collection.find_one(
        {
            "patient_email": patient_email,
        },
        sort=[("_id", -1)],
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="No nurse assessment found for this patient",
        )

    department = document["department"]
    new_priority = update.priority.value
    now = datetime.now(timezone.utc)

    nurse_assessments_collection.update_one(
        {"_id": document["_id"]},
        {
            "$set": {
                "priority": new_priority,
                "updated_at": now,
            }
        },
    )

    queue_entry = get_latest_patient_queue_entry(
        patient_email,
        department,
    )

    # Priority can also be changed while the patient is waiting
    # for reception QR verification.
    allowed_statuses = {
        TRIAGE_STATUS,
        RECEPTION_STATUS,
        *ACTIVE_STATUSES,
    }

    if queue_entry["status"] not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=(
                "Patient is not in a state where triage "
                "priority can be changed"
            ),
        )

    queue_collection.update_one(
        {"_id": queue_entry["_id"]},
        {
            "$set": {
                "priority": new_priority,
                "updated_at": now,
            }
        },
    )

    await recalculate_queue_state(department)

    updated = nurse_assessments_collection.find_one(
        {"_id": document["_id"]}
    )

    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Nurse assessment was not found after updating",
        )

    return NurseAssessmentResponse(
        id=str(updated["_id"]),
        patient_email=updated["patient_email"],
        department=updated["department"],
        doctor_email=updated.get("doctor_email"),
        temperature=updated.get("temperature"),
        pulse=updated.get("pulse"),
        systolic_bp=updated.get("systolic_bp"),
        diastolic_bp=updated.get("diastolic_bp"),
        spo2=updated.get("spo2"),
        pain_level=updated.get("pain_level"),
        symptoms=updated.get("symptoms"),
        nurse_notes=updated.get("nurse_notes"),
        priority=TriagePriority(updated.get(
            "priority",
            TriagePriority.NORMAL.value,
        )),
        created_at=updated["created_at"].isoformat(),
        updated_at=updated["updated_at"].isoformat(),
    )


# ============================================================
# NURSE - ASSIGN / CHANGE DOCTOR
#
# Updates both the nurse assessment and the patient's queue.
# ============================================================

@app.patch(
    f"{settings.api_prefix}/nurse/assessments/{{patient_email}}/doctor",
    response_model=NurseAssessmentResponse,
    tags=["nurse"],
)
async def update_nurse_doctor_assignment(
    patient_email: str,
    update: NurseDoctorAssignmentUpdate,
    current_user: dict[str, str] = Depends(
        require_roles("nurse")
    ),
) -> NurseAssessmentResponse:

    patient_email = (
        patient_email.strip().lower()
    )

    document = nurse_assessments_collection.find_one(
        {
            "patient_email": patient_email,
        },
        sort=[("_id", -1)],
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="No nurse assessment found for this patient",
        )

    department = document["department"]
    doctor_email = ensure_doctor_account(
        update.doctor_email,
        department,
    )
    queue_entry = get_latest_patient_queue_entry(
        patient_email,
        department,
    )

    allowed_statuses = {
        TRIAGE_STATUS,
        *ACTIVE_STATUSES,
    }

    if queue_entry["status"] not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=(
                "Patient is not in a state where the doctor "
                "assignment can be changed"
            ),
        )

    now = datetime.now(timezone.utc)

    nurse_assessments_collection.update_one(
        {"_id": document["_id"]},
        {
            "$set": {
                "doctor_email": doctor_email,
                "updated_at": now,
            }
        },
    )

    queue_update: dict[str, Any] = {
        "doctor_email": doctor_email,
        "updated_at": now,
    }

    # Doctor assignment does not bypass reception verification.
    if queue_entry["status"] in {TRIAGE_STATUS, RECEPTION_STATUS}:
        queue_update["status"] = queue_entry["status"]
        queue_update["position"] = queue_entry.get("position", 0)

    queue_collection.update_one(
        {"_id": queue_entry["_id"]},
        {"$set": queue_update},
    )

    await recalculate_queue_state(department)

    updated = nurse_assessments_collection.find_one(
        {"_id": document["_id"]}
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Nurse assessment not found")

    return NurseAssessmentResponse(
        id=str(updated["_id"]),
        patient_email=updated["patient_email"],
        department=updated["department"],
        doctor_email=updated.get("doctor_email"),
        temperature=updated.get("temperature"),
        pulse=updated.get("pulse"),
        systolic_bp=updated.get("systolic_bp"),
        diastolic_bp=updated.get("diastolic_bp"),
        spo2=updated.get("spo2"),
        pain_level=updated.get("pain_level"),
        symptoms=updated.get("symptoms"),
        nurse_notes=updated.get("nurse_notes"),
        priority=TriagePriority(updated.get(
            "priority",
            TriagePriority.NORMAL.value,
        )),
        created_at=updated["created_at"].isoformat(),
        updated_at=updated["updated_at"].isoformat(),
    )


# ============================================================
# NURSE / DOCTOR - GET ASSESSMENT
# ============================================================

@app.get(
    f"{settings.api_prefix}/nurse/assessments/{{patient_email}}",
    response_model=NurseAssessmentResponse,
    tags=["nurse"],
)
def get_nurse_assessment(
    patient_email: str,
    current_user: dict[str, str] = Depends(
        require_roles(
            "nurse",
            "doctor",
        )
    ),
) -> NurseAssessmentResponse:

    patient_email = (
        patient_email
        .strip()
        .lower()
    )

    document = (
        nurse_assessments_collection.find_one(
            {
                "patient_email":
                    patient_email,
            },
            sort=[
                ("_id", -1)
            ],
        )
    )

    if not document:

        raise HTTPException(
            status_code=404,
            detail=(
                "No nurse assessment found "
                "for this patient"
            ),
        )

    ensure_doctor_assessment_access(
        document,
        current_user,
    )

    return NurseAssessmentResponse(

        id=
            str(
                document["_id"]
            ),

        patient_email=
            document[
                "patient_email"
            ],

        department=
            document[
                "department"
            ],

        doctor_email=
            document.get(
                "doctor_email"
            ),

        temperature=
            document.get(
                "temperature"
            ),

        pulse=
            document.get(
                "pulse"
            ),

        systolic_bp=
            document.get(
                "systolic_bp"
            ),

        diastolic_bp=
            document.get(
                "diastolic_bp"
            ),

        spo2=
            document.get(
                "spo2"
            ),

        pain_level=
            document.get(
                "pain_level"
            ),

        symptoms=
            document.get(
                "symptoms"
            ),

        nurse_notes=
            document.get(
                "nurse_notes"
            ),

        priority=
            TriagePriority(
                document.get(
                    "priority",
                    TriagePriority.NORMAL.value,
                )
            ),

        created_at=
            document[
                "created_at"
            ].isoformat(),

        updated_at=
            document[
                "updated_at"
            ].isoformat(),
    )


# ============================================================
# UPDATE QUEUE STATUS
# ============================================================

@app.patch(
    f"{settings.api_prefix}/queue/{{department}}/{{token_number}}/status",
    response_model=QueueEntryResponse,
    tags=["queue"],
)
async def update_queue_status(
    department: str,
    token_number: int,
    update: QueueStatusUpdate,
    current_user: dict[str, str] = Depends(
        require_roles(
            "doctor",
            "reception",
        )
    ),
) -> QueueEntryResponse:

    department = (
        department.strip()
    )

    queue_entry = queue_collection.find_one(
        {
            "department":
                department,

            "token_number":
                token_number,
        }
    )

    if not queue_entry:

        raise HTTPException(
            status_code=404,
            detail="Queue entry not found",
        )

    ensure_doctor_queue_entry_access(
        queue_entry,
        current_user,
    )

    # --------------------------------------------------------
    # Prevent doctor from moving triage patient directly
    # into consultation.
    # --------------------------------------------------------

    if (
        queue_entry["status"]
        == TRIAGE_STATUS
        and update.status.value
        in {
            QueueStatus.CALLED.value,
            QueueStatus.IN_CONSULTATION.value,
            QueueStatus.COMPLETED.value,
        }
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Patient must complete nurse "
                "assessment before entering "
                "the doctor queue"
            ),
        )

    if current_user["role"] == "doctor":
        validate_doctor_status_transition(
            queue_entry["status"],
            update.status.value,
        )

    queue_collection.update_one(
        {
            "_id":
                queue_entry["_id"]
        },
        {
            "$set": {

                "status":
                    update.status.value,

                "updated_at":
                    datetime.now(
                        timezone.utc
                    ),
            }
        },
    )

    if (
        update.status.value
        not in ACTIVE_STATUSES
    ):

        queue_collection.update_one(
            {
                "_id":
                    queue_entry["_id"]
            },
            {
                "$set": {

                    "position":
                        0,

                    **clear_prediction_fields(),
                }
            },
        )

    updated = queue_collection.find_one(
        {
            "_id":
                queue_entry["_id"]
        }
    )

    if not updated:

        raise HTTPException(
            status_code=404,
            detail=(
                "Queue entry not found "
                "after update"
            ),
        )

    return queue_response(
        updated
    )


# ============================================================
# DOCTOR - CALL PATIENT
# ============================================================

@app.patch(
    f"{settings.api_prefix}/doctor/patients/{{token_number}}/call",
    response_model=QueueEntryResponse,
    tags=["doctor"],
)
async def doctor_call_patient(
    token_number: int,
    current_user: dict[str, str] = Depends(require_roles("doctor")),
) -> QueueEntryResponse:
    doctor_email = current_user["email"].strip().lower()
    queue_entry = queue_collection.find_one(
        {"doctor_email": doctor_email, "token_number": token_number},
        sort=[("_id", -1)],
    )
    if not queue_entry:
        raise HTTPException(status_code=404, detail="Patient not found in your queue")

    validate_doctor_status_transition(
        queue_entry["status"],
        QueueStatus.CALLED.value,
    )
    queue_collection.update_one(
        {"_id": queue_entry["_id"]},
        {"$set": {
            "status": QueueStatus.CALLED.value,
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    await recalculate_queue_state(queue_entry["department"])
    updated_entry = queue_collection.find_one({"_id": queue_entry["_id"]})
    if not updated_entry:
        raise HTTPException(status_code=404, detail="Queue entry not found")

    try:
        asyncio.create_task(
            maybe_send_sms_queue_notification(
                updated_entry,
                users_collection,
                queue_collection,
                force_status=QueueStatus.CALLED.value,
            )
        )
        asyncio.create_task(
            maybe_send_patient_fcm_notification(
                updated_entry,
                users_collection,
                force_status=QueueStatus.CALLED.value,
            )
        )
    except Exception:
        pass

    return queue_response(updated_entry)


# ============================================================
# DOCTOR - START CONSULTATION
# ============================================================

@app.patch(
    f"{settings.api_prefix}/doctor/patients/{{token_number}}/start",
    response_model=QueueEntryResponse,
    tags=["doctor"],
)
async def doctor_start_consultation(
    token_number: int,
    current_user: dict[str, str] = Depends(require_roles("doctor")),
) -> QueueEntryResponse:
    doctor_email = current_user["email"].strip().lower()
    queue_entry = queue_collection.find_one(
        {"doctor_email": doctor_email, "token_number": token_number},
        sort=[("_id", -1)],
    )
    if not queue_entry:
        raise HTTPException(status_code=404, detail="Patient not found in your queue")

    validate_doctor_status_transition(
        queue_entry["status"],
        QueueStatus.IN_CONSULTATION.value,
    )
    queue_collection.update_one(
        {"_id": queue_entry["_id"]},
        {"$set": {
            "status": QueueStatus.IN_CONSULTATION.value,
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    await recalculate_queue_state(queue_entry["department"])
    updated_entry = queue_collection.find_one({"_id": queue_entry["_id"]})
    if not updated_entry:
        raise HTTPException(status_code=404, detail="Queue entry not found")
    return queue_response(updated_entry)


# ============================================================
# DOCTOR - GET CONSULTATION
# ============================================================

@app.get(
    f"{settings.api_prefix}/doctor/patients/{{token_number}}/consultation",
    response_model=DoctorConsultationResponse,
    tags=["doctor"],
)
def get_doctor_consultation(
    token_number: int,
    current_user: dict[str, str] = Depends(require_roles("doctor")),
) -> DoctorConsultationResponse:
    doctor_email = current_user["email"].strip().lower()

    queue_entry = queue_collection.find_one(
        {
            "doctor_email": doctor_email,
            "token_number": token_number,
        },
        sort=[("_id", -1)],
    )

    if not queue_entry:
        raise HTTPException(
            status_code=404,
            detail="Patient not found in your queue",
        )

    consultation = doctor_consultations_collection.find_one(
        {
            "queue_entry_id": str(queue_entry["_id"]),
            "doctor_email": doctor_email,
        }
    )

    if not consultation:
        now_iso = datetime.now(timezone.utc).isoformat()
        return DoctorConsultationResponse(
            id="",
            token_number=token_number,
            patient_email=queue_entry.get("patient_email", ""),
            department=queue_entry.get("department", ""),
            doctor_email=doctor_email,
            diagnosis="",
            consultation_notes="",
            prescription="",
            treatment_advice="",
            started_at=None,
            completed_at=None,
            created_at=now_iso,
            updated_at=now_iso,
        )

    return DoctorConsultationResponse(
        id=str(consultation["_id"]),
        token_number=consultation["token_number"],
        patient_email=consultation["patient_email"],
        department=consultation["department"],
        doctor_email=consultation["doctor_email"],
        diagnosis=consultation.get("diagnosis", ""),
        consultation_notes=consultation.get("consultation_notes", ""),
        prescription=consultation.get("prescription", ""),
        treatment_advice=consultation.get("treatment_advice", ""),
        started_at=(
            consultation["started_at"].isoformat()
            if consultation.get("started_at")
            else None
        ),
        completed_at=(
            consultation["completed_at"].isoformat()
            if consultation.get("completed_at")
            else None
        ),
        created_at=consultation["created_at"].isoformat(),
        updated_at=consultation["updated_at"].isoformat(),
    )


# ============================================================
# DOCTOR - SAVE CONSULTATION
# ============================================================

@app.put(
    f"{settings.api_prefix}/doctor/patients/{{token_number}}/consultation",
    response_model=DoctorConsultationResponse,
    tags=["doctor"],
)
def save_doctor_consultation(
    token_number: int,
    consultation_data: DoctorConsultationCreate,
    current_user: dict[str, str] = Depends(require_roles("doctor")),
) -> DoctorConsultationResponse:
    doctor_email = current_user["email"].strip().lower()

    queue_entry = queue_collection.find_one(
        {
            "doctor_email": doctor_email,
            "token_number": token_number,
        },
        sort=[("_id", -1)],
    )

    if not queue_entry:
        raise HTTPException(
            status_code=404,
            detail="Patient not found in your queue",
        )

    if queue_entry["status"] != QueueStatus.IN_CONSULTATION.value:
        raise HTTPException(
            status_code=400,
            detail="Consultation details can only be saved while the patient is in consultation.",
        )

    now = datetime.now(timezone.utc)
    queue_entry_id = str(queue_entry["_id"])

    doctor_consultations_collection.update_one(
        {
            "queue_entry_id": queue_entry_id,
            "doctor_email": doctor_email,
        },
        {
            "$set": {
                "token_number": token_number,
                "patient_email": queue_entry["patient_email"],
                "department": queue_entry["department"],
                "doctor_email": doctor_email,
                "diagnosis": consultation_data.diagnosis.strip(),
                "consultation_notes": consultation_data.consultation_notes.strip(),
                "prescription": consultation_data.prescription.strip(),
                "treatment_advice": consultation_data.treatment_advice.strip(),
                "updated_at": now,
            },
            "$setOnInsert": {
                "queue_entry_id": queue_entry_id,
                "started_at": now,
                "completed_at": None,
                "created_at": now,
            },
        },
        upsert=True,
    )

    saved = doctor_consultations_collection.find_one(
        {
            "queue_entry_id": queue_entry_id,
            "doctor_email": doctor_email,
        }
    )

    if not saved:
        raise HTTPException(
            status_code=500,
            detail="Consultation could not be saved.",
        )

    return DoctorConsultationResponse(
        id=str(saved["_id"]),
        token_number=saved["token_number"],
        patient_email=saved["patient_email"],
        department=saved["department"],
        doctor_email=saved["doctor_email"],
        diagnosis=saved.get("diagnosis", ""),
        consultation_notes=saved.get("consultation_notes", ""),
        prescription=saved.get("prescription", ""),
        treatment_advice=saved.get("treatment_advice", ""),
        started_at=(
            saved["started_at"].isoformat()
            if saved.get("started_at")
            else None
        ),
        completed_at=(
            saved["completed_at"].isoformat()
            if saved.get("completed_at")
            else None
        ),
        created_at=saved["created_at"].isoformat(),
        updated_at=saved["updated_at"].isoformat(),
    )


# ============================================================
# DOCTOR - COMPLETE CONSULTATION
# ============================================================

@app.patch(
    f"{settings.api_prefix}/doctor/patients/{{token_number}}/complete",
    response_model=QueueEntryResponse,
    tags=["doctor"],
)
async def doctor_complete_consultation(
    token_number: int,
    current_user: dict[str, str] = Depends(require_roles("doctor")),
) -> QueueEntryResponse:
    doctor_email = current_user["email"].strip().lower()
    queue_entry = queue_collection.find_one(
        {"doctor_email": doctor_email, "token_number": token_number},
        sort=[("_id", -1)],
    )
    if not queue_entry:
        raise HTTPException(status_code=404, detail="Patient not found in your queue")

    validate_doctor_status_transition(
        queue_entry["status"],
        QueueStatus.COMPLETED.value,
    )

    consultation = doctor_consultations_collection.find_one(
        {
            "queue_entry_id": str(queue_entry["_id"]),
            "doctor_email": doctor_email,
        }
    )

    if not consultation:
        raise HTTPException(
            status_code=400,
            detail="Please start the consultation and save the consultation details before completing.",
        )

    diagnosis = (consultation.get("diagnosis", "") or "").strip()
    if not diagnosis:
        raise HTTPException(
            status_code=400,
            detail="Diagnosis is required before completing the consultation.",
        )

    now = datetime.now(timezone.utc)

    doctor_consultations_collection.update_one(
        {"_id": consultation["_id"]},
        {
            "$set": {
                "completed_at": now,
                "updated_at": now,
            }
        },
    )

    queue_collection.update_one(
        {"_id": queue_entry["_id"]},
        {"$set": {
            "status": QueueStatus.COMPLETED.value,
            "position": 0,
            "updated_at": now,
            **clear_prediction_fields(),
        }},
    )
    await recalculate_queue_state(queue_entry["department"])

    updated_entry = queue_collection.find_one({"_id": queue_entry["_id"]})
    if not updated_entry:
        raise HTTPException(status_code=404, detail="Updated queue entry not found")

    return queue_response(updated_entry)


# ============================================================
# SKIP PATIENT
# ============================================================

@app.patch(
    f"{settings.api_prefix}/queue/{{department}}/{{token_number}}/skip",
    response_model=QueueEntryResponse,
    tags=["queue"],
)
async def skip_queue_patient(
    department: str,
    token_number: int,
    current_user: dict[str, str] = Depends(
        require_roles(
            "doctor",
            "reception",
        )
    ),
) -> QueueEntryResponse:

    department = (
        department.strip()
    )

    queue_entry = queue_collection.find_one(
        {
            "department":
                department,

            "token_number":
                token_number,
        }
    )

    if not queue_entry:

        raise HTTPException(
            status_code=404,
            detail="Queue entry not found",
        )

    ensure_doctor_queue_entry_access(
        queue_entry,
        current_user,
    )

    if queue_entry["status"] not in {
        QueueStatus.WAITING.value,
        QueueStatus.CALLED.value,
        QueueStatus.IN_CONSULTATION.value,
    }:

        raise HTTPException(
            status_code=400,
            detail=(
                "Only waiting, called, or in-consultation patients "
                "can be skipped"
            ),
        )

    queue_collection.update_one(
        {
            "_id":
                queue_entry["_id"]
        },
        {
            "$set": {

                "status":
                    QueueStatus.SKIPPED.value,

                "position":
                    0,

                "updated_at":
                    datetime.now(
                        timezone.utc
                    ),

                **clear_prediction_fields(),
            }
        },
    )

    await recalculate_queue_state(
        department
    )

    doctor_email = (queue_entry.get("doctor_email") or "").strip().lower()
    if doctor_email:
        doctor = users_collection.find_one(
            {"email": doctor_email, "role": "doctor"},
            {"name": 1, "queue_capacity": 1},
        ) or {}
        capacity = int(doctor.get("queue_capacity") or DEFAULT_QUEUE_CAPACITY)
        active_count = queue_collection.count_documents(
            {
                "doctor_email": doctor_email,
                "status": {"$in": list(DOCTOR_CAPACITY_STATUSES)},
            }
        )
        if active_count < capacity:
            next_patient = queue_collection.find_one(
                {
                    "doctor_email": doctor_email,
                    "status": TRIAGE_STATUS,
                },
                sort=[("position", 1), ("created_at", 1)],
            )
            if next_patient:
                await send_notification(
                    next_patient["patient_email"],
                    notification_type="DOCTOR_SLOT_AVAILABLE",
                    title="Doctor slot available",
                    message=(
                        f"A queue slot is now available with Dr. "
                        f"{doctor.get('name') or doctor_email}."
                    ),
                    data={
                        "doctor_email": doctor_email,
                        "department": department,
                        "queue_count": active_count,
                        "queue_capacity": capacity,
                    },
                )

    updated = queue_collection.find_one(
        {
            "_id":
                queue_entry["_id"]
        }
    )

    if not updated:

        raise HTTPException(
            status_code=404,
            detail=(
                "Queue entry not found "
                "after skip"
            ),
        )

    try:
        asyncio.create_task(
            maybe_send_sms_queue_notification(
                updated,
                users_collection,
                queue_collection,
                force_status=QueueStatus.SKIPPED.value,
                force_position=0,
            )
        )
        asyncio.create_task(
            maybe_send_patient_fcm_notification(
                updated,
                users_collection,
                force_status=QueueStatus.SKIPPED.value,
                force_position=0,
            )
        )
    except Exception:
        pass

    return queue_response(
        updated
    )


# ============================================================
# REQUEUE SKIPPED PATIENT
# ============================================================

@app.patch(
    f"{settings.api_prefix}/queue/{{department}}/{{token_number}}/requeue",
    response_model=QueueEntryResponse,
    tags=["queue"],
)
async def requeue_queue_patient(
    department: str,
    token_number: int,
    current_user: dict[str, str] = Depends(
        require_roles(
            "doctor",
            "reception",
        )
    ),
) -> QueueEntryResponse:

    department = (
        department.strip()
    )

    queue_entry = queue_collection.find_one(
        {
            "department":
                department,

            "token_number":
                token_number,
        }
    )

    if not queue_entry:

        raise HTTPException(
            status_code=404,
            detail="Queue entry not found",
        )

    ensure_doctor_queue_entry_access(
        queue_entry,
        current_user,
    )

    if (
        queue_entry["status"]
        != QueueStatus.SKIPPED.value
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Only skipped patients "
                "can be requeued"
            ),
        )

    active_count = (
        queue_collection.count_documents(
            {
                "department":
                    department,

                "status": {
                    "$in":
                        list(
                            ACTIVE_STATUSES
                        )
                },
            }
        )
    )

    queue_collection.update_one(
        {
            "_id":
                queue_entry["_id"]
        },
        {
            "$set": {

                "status":
                    QueueStatus.WAITING.value,

                "position":
                    active_count + 1,

                "updated_at":
                    datetime.now(
                        timezone.utc
                    ),
            }
        },
    )

    await recalculate_queue_state(
        department
    )

    updated = queue_collection.find_one(
        {
            "_id":
                queue_entry["_id"]
        }
    )

    if not updated:

        raise HTTPException(
            status_code=404,
            detail=(
                "Queue entry not found "
                "after requeue"
            ),
        )

    try:
        asyncio.create_task(
            maybe_send_sms_queue_notification(
                updated,
                users_collection,
                queue_collection,
                force_status=QueueStatus.WAITING.value,
            )
        )
        asyncio.create_task(
            maybe_send_patient_fcm_notification(
                updated,
                users_collection,
                force_status=QueueStatus.WAITING.value,
            )
        )
    except Exception:
        pass

    return queue_response(
        updated
    )


# ============================================================
# RECEPTION - GENERATE PATIENT QUEUE QR
#
# Reception displays this QR for a patient who completed nurse
# triage. The patient scans it from the patient dashboard.
# ============================================================

@app.post(
    f"{settings.api_prefix}/queue/{{department}}/{{token_number}}/qr",
    response_model=QRTokenResponse,
    tags=["qr"],
)
def generate_queue_qr(
    department: str,
    token_number: int,
    current_user: dict[str, str] = Depends(
        require_roles("reception")
    ),
) -> QRTokenResponse:
    clean_department = department.strip()

    dept_filter = [clean_department]
    if clean_department.lower() in ["general", "general medicine"]:
        dept_filter = ["General", "General Medicine"]

    # Match patient by token and department (or any dept for this token if needed)
    queue_entry = queue_collection.find_one(
        {
            "token_number": token_number,
            "$or": [
                {"department": {"$in": dept_filter}},
                {"department": clean_department},
            ],
            "status": {
                "$in": [
                    QueueStatus.WAITING_FOR_RECEPTION.value,
                    QueueStatus.WAITING.value,
                ]
            },
            "queue_access_verified": {"$ne": True},
        },
        sort=[("_id", -1)],
    )

    if not queue_entry:
        # Fallback query if department string differs slightly
        queue_entry = queue_collection.find_one(
            {
                "token_number": token_number,
                "status": {
                    "$in": [
                        QueueStatus.WAITING_FOR_RECEPTION.value,
                        QueueStatus.WAITING.value,
                    ]
                },
                "queue_access_verified": {"$ne": True},
            },
            sort=[("_id", -1)],
        )

    if not queue_entry:
        raise HTTPException(
            status_code=404,
            detail="Patient is not waiting for reception QR verification.",
        )

    # Ensure status is properly WAITING_FOR_RECEPTION until patient scans
    if queue_entry.get("status") != QueueStatus.WAITING_FOR_RECEPTION.value:
        queue_collection.update_one(
            {"_id": queue_entry["_id"]},
            {"$set": {
                "status": QueueStatus.WAITING_FOR_RECEPTION.value,
                "position": 0,
                "queue_access_verified": False,
                "updated_at": datetime.now(timezone.utc),
            }}
        )
        queue_entry["status"] = QueueStatus.WAITING_FOR_RECEPTION.value

    raw_token = generate_qr_token()
    token_hash = hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()
    manual_code = f"{secrets.randbelow(1_000_000):06d}"

    manual_code_hash = hashlib.sha256(
        manual_code.encode("utf-8")
    ).hexdigest()
    created_at = datetime.now(timezone.utc)
    expires_at = created_at + timedelta(minutes=15)

    # One active QR per queue entry.
    qr_tokens_collection.delete_many(
        {
            "queue_entry_id": str(queue_entry["_id"]),
            "used_at": {"$exists": False},
        }
    )

    qr_tokens_collection.insert_one(
    {
        "token_hash": token_hash,
        "manual_code_hash": manual_code_hash,
        "queue_entry_id": str(queue_entry["_id"]),
        "department": queue_entry["department"],
        "token_number": queue_entry["token_number"],
        "expires_at": expires_at,
        "created_at": created_at,
        "created_by": current_user["email"],
        "created_by_role": "reception",
    }
)

    return QRTokenResponse(
    qr_image_data=generate_qr_image_data(raw_token),
    verification_code=raw_token,
    manual_code=manual_code,
    expires_at=expires_at,
)


# ============================================================
# PATIENT - VERIFY RECEPTION QR
#
# The patient scans the QR displayed by reception. On success the
# queue entry moves from WAITING_FOR_RECEPTION to WAITING and the
# doctor queue/ML state is recalculated.
# ============================================================

@app.post(
    f"{settings.api_prefix}/qr/verify",
    response_model=QRVerificationResponse,
    tags=["qr"],
)
async def verify_reception_qr(
    request: QRVerificationRequest,
    current_user: dict[str, str] = Depends(
        require_roles("patient")
    ),
) -> QRVerificationResponse:
    submitted_token = (request.token or "").strip()
    submitted_code = (request.manual_code or "").strip()

    # If only one value provided and it's 6 digits, it might be passed as token
    if not submitted_code and submitted_token.isdigit() and len(submitted_token) == 6:
        submitted_code = submitted_token

    if not submitted_token and not submitted_code:
        raise HTTPException(
            status_code=422,
            detail="QR token or 6-digit code is required.",
        )

    now = datetime.now(timezone.utc)
    qr_query = {
        "expires_at": {"$gt": now},
        "used_at": {"$exists": False},
    }

    if submitted_code:
        code_hash = hashlib.sha256(submitted_code.encode("utf-8")).hexdigest()
        qr_query["manual_code_hash"] = code_hash
    else:
        token_hash = hashlib.sha256(submitted_token.encode("utf-8")).hexdigest()
        qr_query["token_hash"] = token_hash

    qr_record = qr_tokens_collection.find_one(qr_query)

    if not qr_record:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired verification code / QR token.",
        )

    queue_entry = queue_collection.find_one(
        {"_id": ObjectId(qr_record["queue_entry_id"])}
    )

    if not queue_entry:
        raise HTTPException(
            status_code=404,
            detail="Queue entry not found.",
        )

    patient_email = current_user["email"].strip().lower()
    if queue_entry.get("patient_email", "").strip().lower() != patient_email:
        raise HTTPException(
            status_code=403,
            detail="This QR code does not belong to your queue entry.",
        )

    if queue_entry.get("status") != QueueStatus.WAITING_FOR_RECEPTION.value:
        raise HTTPException(
            status_code=400,
            detail="Your queue is not waiting for reception verification.",
        )

    queue_collection.update_one(
        {"_id": queue_entry["_id"]},
        {
            "$set": {
                "queue_access_verified": True,
                "status": QueueStatus.WAITING.value,
                "position": 0,
                "updated_at": now,
            }
        },
    )

    qr_tokens_collection.update_one(
        {"_id": qr_record["_id"]},
        {
            "$set": {
                "used_at": now,
                "verified_by": patient_email,
                "verified_by_role": "patient",
            }
        },
    )

    await recalculate_queue_state(queue_entry["department"])

    updated = queue_collection.find_one({"_id": queue_entry["_id"]})
    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Queue entry not found after verification.",
        )

    return QRVerificationResponse(
        valid=True,
        patient_email=updated["patient_email"],
        department=updated["department"],
        token_number=updated["token_number"],
        status=updated["status"],
    )


# ============================================================
# PAST MEDICAL RECORDS (READ-ONLY)
# ============================================================

def patient_has_past_records(patient_email: str | None) -> bool:
    """Check whether a patient has any completed historical medical records."""
    if not patient_email:
        return False
    clean_email = patient_email.strip().lower()
    if not clean_email:
        return False
    if queue_collection.find_one({"patient_email": clean_email, "status": QueueStatus.COMPLETED.value}, {"_id": 1}):
        return True
    if doctor_consultations_collection.find_one({"patient_email": clean_email, "completed_at": {"$ne": None}}, {"_id": 1}):
        return True
    return False


def fetch_patient_past_medical_records(patient_email: str) -> dict[str, Any]:
    """Retrieve completed historical medical interactions for a patient.
    Excludes active/live consultations and uncompleted queue entries."""
    clean_email = patient_email.strip().lower()

    # Find completed queue entries for this patient
    completed_entries = list(
        queue_collection.find(
            {
                "patient_email": clean_email,
                "status": QueueStatus.COMPLETED.value,
            }
        ).sort("created_at", -1)
    )

    records: list[dict[str, Any]] = []

    for entry in completed_entries:
        entry_id_str = str(entry["_id"])
        created_dt = entry.get("created_at") or entry.get("updated_at")

        # Find corresponding doctor consultation
        consultation = doctor_consultations_collection.find_one(
            {"queue_entry_id": entry_id_str}
        )
        if not consultation:
            # Fallback: look for consultation by patient_email and department
            consultation = doctor_consultations_collection.find_one(
                {
                    "patient_email": clean_email,
                    "department": entry.get("department"),
                    "completed_at": {"$ne": None},
                },
                sort=[("_id", -1)],
            )

        # Look up doctor name if doctor_email exists
        doc_email = (
            (consultation.get("doctor_email") if consultation else None)
            or entry.get("doctor_email")
            or ""
        )
        doc_name = doc_email
        if doc_email:
            doc_user = users_collection.find_one(
                {"email": doc_email.strip().lower()},
                {"_id": 0, "name": 1, "full_name": 1},
            )
            if doc_user:
                doc_name = doc_user.get("name") or doc_user.get("full_name") or doc_email

        # Find corresponding nurse assessment
        nurse_assessment_doc = nurse_assessments_collection.find_one(
            {
                "patient_email": clean_email,
                "department": entry.get("department"),
                "created_at": {"$lte": created_dt if created_dt else datetime.now(timezone.utc)},
            },
            sort=[("created_at", -1)],
        )

        nurse_summary: dict[str, Any] | None = None
        if nurse_assessment_doc:
            nurse_summary = {
                "priority": nurse_assessment_doc.get("priority", "normal"),
                "symptoms": nurse_assessment_doc.get("symptoms", ""),
                "nurse_notes": nurse_assessment_doc.get("nurse_notes", ""),
                "temperature": nurse_assessment_doc.get("temperature"),
                "pulse": nurse_assessment_doc.get("pulse"),
                "systolic_bp": nurse_assessment_doc.get("systolic_bp"),
                "diastolic_bp": nurse_assessment_doc.get("diastolic_bp"),
                "spo2": nurse_assessment_doc.get("spo2"),
                "pain_level": nurse_assessment_doc.get("pain_level"),
            }

        # Date formatting
        date_val = (
            consultation.get("completed_at")
            if consultation and consultation.get("completed_at")
            else created_dt
        )
        date_str = ""
        if isinstance(date_val, datetime):
            date_str = date_val.strftime("%d %b %Y")
        elif isinstance(date_val, str):
            date_str = date_val
        else:
            date_str = "Completed Visit"

        record_id = (
            str(consultation["_id"])
            if consultation and "_id" in consultation
            else entry_id_str
        )

        records.append({
            "record_id": record_id,
            "date": date_str,
            "doctor_email": doc_email,
            "doctor_name": doc_name,
            "department": entry.get("department", "General"),
            "diagnosis": consultation.get("diagnosis", "") if consultation else "",
            "consultation_notes": consultation.get("consultation_notes", "") if consultation else "",
            "prescription": consultation.get("prescription", "") if consultation else "",
            "treatment_advice": consultation.get("treatment_advice", "") if consultation else "",
            "nurse_assessment": nurse_summary,
        })

    # Also include completed consultations that might not have matching queue_entries anymore
    existing_record_ids = {r["record_id"] for r in records}
    completed_consultations = list(
        doctor_consultations_collection.find(
            {
                "patient_email": clean_email,
                "completed_at": {"$ne": None},
            }
        ).sort("completed_at", -1)
    )

    for c in completed_consultations:
        c_id = str(c["_id"])
        if c_id in existing_record_ids:
            continue

        c_date = c.get("completed_at") or c.get("created_at")
        date_str = ""
        if isinstance(c_date, datetime):
            date_str = c_date.strftime("%d %b %Y")
        elif isinstance(c_date, str):
            date_str = c_date
        else:
            date_str = "Completed Visit"

        doc_email = c.get("doctor_email", "")
        doc_name = doc_email
        if doc_email:
            doc_user = users_collection.find_one(
                {"email": doc_email.strip().lower()},
                {"_id": 0, "name": 1, "full_name": 1},
            )
            if doc_user:
                doc_name = doc_user.get("name") or doc_user.get("full_name") or doc_email

        records.append({
            "record_id": c_id,
            "date": date_str,
            "doctor_email": doc_email,
            "doctor_name": doc_name,
            "department": c.get("department", "General"),
            "diagnosis": c.get("diagnosis", ""),
            "consultation_notes": c.get("consultation_notes", ""),
            "prescription": c.get("prescription", ""),
            "treatment_advice": c.get("treatment_advice", ""),
            "nurse_assessment": None,
        })

    return {"records": records}


# PATIENT - VIEW OWN PAST MEDICAL RECORDS
@app.get(
    f"{settings.api_prefix}/patient/medical-history",
    tags=["patient"],
)
def get_patient_medical_history(
    current_user: dict[str, str] = Depends(require_roles("patient")),
) -> dict[str, Any]:
    patient_email = current_user["email"].strip().lower()
    return fetch_patient_past_medical_records(patient_email)


# NURSE - VIEW PATIENT PAST MEDICAL RECORDS
@app.get(
    f"{settings.api_prefix}/nurse/patient/{{patient_identifier}}/medical-history",
    tags=["nurse"],
)
def get_nurse_patient_medical_history(
    patient_identifier: str,
    current_user: dict[str, str] = Depends(require_roles("nurse")),
) -> dict[str, Any]:
    clean_identifier = patient_identifier.strip().lower()

    # The nurse can lookup by email or token_number
    target_email = clean_identifier
    if clean_identifier.isdigit():
        q_entry = queue_collection.find_one(
            {"token_number": int(clean_identifier)},
            sort=[("_id", -1)],
        )
        if q_entry:
            target_email = q_entry.get("patient_email", clean_identifier)

    # Verify patient exists
    patient_exists = (
        users_collection.find_one({"email": target_email})
        or queue_collection.find_one({"patient_email": target_email})
        or nurse_assessments_collection.find_one({"patient_email": target_email})
    )
    if not patient_exists:
        raise HTTPException(
            status_code=404,
            detail="Patient not found",
        )

    return fetch_patient_past_medical_records(target_email)


# DOCTOR - VIEW ASSIGNED PATIENT PAST MEDICAL RECORDS
@app.get(
    f"{settings.api_prefix}/doctor/patient/{{patient_identifier}}/medical-history",
    tags=["doctor"],
)
def get_doctor_patient_medical_history(
    patient_identifier: str,
    current_user: dict[str, str] = Depends(require_roles("doctor")),
) -> dict[str, Any]:
    doctor_email = current_user["email"].strip().lower()
    clean_identifier = patient_identifier.strip().lower()

    # Check if patient_identifier is a token or email
    target_email = clean_identifier
    if clean_identifier.isdigit():
        token_num = int(clean_identifier)
        assigned_entry = queue_collection.find_one(
            {
                "doctor_email": doctor_email,
                "token_number": token_num,
            },
            sort=[("_id", -1)],
        )
        if not assigned_entry:
            raise HTTPException(
                status_code=403,
                detail="Doctor does not have access to this patient",
            )
        target_email = assigned_entry.get("patient_email", "")
    else:
        assigned_entry = queue_collection.find_one(
            {
                "doctor_email": doctor_email,
                "patient_email": clean_identifier,
            },
            sort=[("_id", -1)],
        )
        if not assigned_entry:
            raise HTTPException(
                status_code=403,
                detail="Doctor does not have access to this patient",
            )

    return fetch_patient_past_medical_records(target_email)


# ============================================================
# PATIENT - SMS NOTIFICATION PREFERENCES
# ============================================================

@app.get(
    f"{settings.api_prefix}/patient/sms-preferences",
    response_model=PatientSmsPreferencesResponse,
    tags=["patient"],
)
@app.get(
    f"{settings.api_prefix}/patient/whatsapp-preferences",
    response_model=PatientSmsPreferencesResponse,
    tags=["patient"],
    include_in_schema=False,
)
def get_patient_sms_preferences(
    current_user: dict[str, str] = Depends(require_roles("patient")),
) -> PatientSmsPreferencesResponse:
    patient_email = current_user["email"].strip().lower()
    user = users_collection.find_one(
        {"email": patient_email},
        {"phone_number": 1, "sms_opt_in": 1, "whatsapp_number": 1, "whatsapp_opt_in": 1},
    )
    if not user:
        raise HTTPException(status_code=404, detail="User account not found")

    phone = user.get("phone_number") or user.get("whatsapp_number")
    opt_in = bool(user.get("sms_opt_in", False) or user.get("whatsapp_opt_in", False))

    return PatientSmsPreferencesResponse(
        phone_number=phone,
        sms_opt_in=opt_in,
    )


@app.put(
    f"{settings.api_prefix}/patient/sms-preferences",
    response_model=PatientSmsPreferencesResponse,
    tags=["patient"],
)
@app.put(
    f"{settings.api_prefix}/patient/whatsapp-preferences",
    response_model=PatientSmsPreferencesResponse,
    tags=["patient"],
    include_in_schema=False,
)
def update_patient_sms_preferences(
    preferences: PatientSmsPreferencesUpdate,
    current_user: dict[str, str] = Depends(require_roles("patient")),
) -> PatientSmsPreferencesResponse:
    patient_email = current_user["email"].strip().lower()

    raw_phone = preferences.phone_number
    clean_number = None
    if raw_phone:
        clean_number = normalize_phone_number(raw_phone)
        if not clean_number:
            raise HTTPException(
                status_code=400,
                detail="Invalid mobile number format. Please provide a valid 10-digit mobile number.",
            )

    # If opt_in is requested, require a valid phone number
    opt_in = bool(preferences.sms_opt_in)
    if opt_in and not clean_number:
        # Check if existing number exists
        existing_user = users_collection.find_one(
            {"email": patient_email},
            {"phone_number": 1, "whatsapp_number": 1},
        )
        existing_number = existing_user.get("phone_number") or existing_user.get("whatsapp_number") if existing_user else None
        if not existing_number:
            raise HTTPException(
                status_code=400,
                detail="A valid phone number is required to enable SMS notifications.",
            )
        clean_number = existing_number

    update_doc: dict[str, Any] = {
        "sms_opt_in": opt_in,
        "whatsapp_opt_in": opt_in,
        "updated_at": datetime.now(timezone.utc),
    }
    if clean_number is not None:
        update_doc["phone_number"] = clean_number
        update_doc["whatsapp_number"] = clean_number

    users_collection.update_one(
        {"email": patient_email},
        {"$set": update_doc},
    )

    updated_user = users_collection.find_one(
        {"email": patient_email},
        {"phone_number": 1, "sms_opt_in": 1, "whatsapp_number": 1, "whatsapp_opt_in": 1},
    ) or {}

    return PatientSmsPreferencesResponse(
        phone_number=updated_user.get("phone_number") or updated_user.get("whatsapp_number"),
        sms_opt_in=bool(updated_user.get("sms_opt_in", False) or updated_user.get("whatsapp_opt_in", False)),
    )


# ============================================================
# PATIENT - FCM PUSH NOTIFICATION PREFERENCES & TOKEN
# ============================================================

@app.get(
    f"{settings.api_prefix}/patient/fcm-preferences",
    response_model=PatientFcmPreferencesResponse,
    tags=["patient"],
)
def get_patient_fcm_preferences(
    current_user: dict[str, str] = Depends(require_roles("patient")),
) -> PatientFcmPreferencesResponse:
    patient_email = current_user["email"].strip().lower()
    user = users_collection.find_one(
        {"email": patient_email},
        {"fcm_token": 1, "notifications_enabled": 1, "fcm_token_updated_at": 1},
    )
    if not user:
        raise HTTPException(status_code=404, detail="User account not found")

    token_exists = bool(user.get("fcm_token"))
    enabled = bool(user.get("notifications_enabled", False))
    updated_at = user.get("fcm_token_updated_at")
    updated_at_str = (
        updated_at.isoformat() if isinstance(updated_at, datetime) else str(updated_at) if updated_at else None
    )

    return PatientFcmPreferencesResponse(
        fcm_token_registered=token_exists,
        notifications_enabled=enabled,
        fcm_token_updated_at=updated_at_str,
    )


@app.post(
    f"{settings.api_prefix}/patient/fcm-token",
    response_model=PatientFcmPreferencesResponse,
    tags=["patient"],
)
def update_patient_fcm_token(
    payload: PatientFcmTokenUpdate,
    current_user: dict[str, str] = Depends(require_roles("patient")),
) -> PatientFcmPreferencesResponse:
    patient_email = current_user["email"].strip().lower()

    now = datetime.now(timezone.utc)
    users_collection.update_one(
        {"email": patient_email},
        {
            "$set": {
                "fcm_token": payload.fcm_token.strip(),
                "notifications_enabled": payload.notifications_enabled,
                "fcm_token_updated_at": now,
                "updated_at": now,
            }
        },
    )

    return PatientFcmPreferencesResponse(
        fcm_token_registered=True,
        notifications_enabled=payload.notifications_enabled,
        fcm_token_updated_at=now.isoformat(),
    )
