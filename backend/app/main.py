import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pymongo import MongoClient

from app.qr import generate_qr_image_data, generate_qr_token

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
from app.queue_schemas import (
    QueueEntryCreate,
    QueueEntryResponse,
    QueueStatus,
    QueueStatusUpdate,
)

from app.schemas import (
    StaffUserCreate,
    UserCreate,
    UserLogin,
    UserResponse,
)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Smart QR-Based Hospital Patient Journey Management System.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

mongo_client = MongoClient(
    settings.mongodb_uri,
    serverSelectionTimeoutMS=2000,
)

database = mongo_client.get_database()
users_collection = database["users"]
queue_collection = database["queue_entries"]
qr_tokens_collection = database["qr_tokens"]


@app.get(f"{settings.api_prefix}/db-health", tags=["system"])
def database_health() -> dict[str, str]:
    try:
        mongo_client.admin.command("ping")
        return {"status": "ok", "database": "MongoDB connected"}
    except Exception:
        return {"status": "error", "database": "MongoDB unavailable"}


@app.get(f"{settings.api_prefix}/health", tags=["system"])
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "phase": "4",
    }


@app.post(
    f"{settings.api_prefix}/auth/register",
    response_model=UserResponse,
    status_code=201,
    tags=["authentication"],
)
def register_patient(user: UserCreate) -> UserResponse:
    email = user.email.strip().lower()

    existing_user = users_collection.find_one(
        {"email": email},
        {"_id": 1},
    )

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists",
        )

    users_collection.insert_one(
        {
            "email": email,
            "password_hash": hash_password(user.password),
            "role": "patient",
        }
    )

    return UserResponse(
        email=email,
        role="patient",
    )


@app.post(
    f"{settings.api_prefix}/auth/login",
    tags=["authentication"],
)
def login_user(user: UserLogin) -> dict[str, str]:
    email = user.email.strip().lower()

    stored_user = users_collection.find_one({"email": email})

    if not stored_user or not verify_password(
        user.password,
        stored_user["password_hash"],
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


@app.get(
    f"{settings.api_prefix}/auth/me",
    tags=["authentication"],
)
def get_logged_in_user(
    current_user: dict[str, str] = Depends(get_current_user),
) -> dict[str, str]:
    return current_user


@app.get(
    f"{settings.api_prefix}/patient-area",
    tags=["authorization"],
)
def patient_area(
    current_user: dict[str, str] = Depends(require_roles("patient")),
) -> dict[str, str]:
    return {
        "message": "Patient area accessed successfully",
        "email": current_user["email"],
        "role": current_user["role"],
    }


@app.post(
    f"{settings.api_prefix}/admin/users",
    response_model=UserResponse,
    status_code=201,
    tags=["administration"],
)
def create_staff_user(
    user: StaffUserCreate,
    current_user: dict[str, str] = Depends(require_roles("admin")),
) -> UserResponse:
    email = user.email.strip().lower()

    existing_user = users_collection.find_one(
        {"email": email},
        {"_id": 1},
    )

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists",
        )

    users_collection.insert_one(
        {
            "email": email,
            "password_hash": hash_password(user.password),
            "role": user.role.value,
        }
    )

    return UserResponse(
        email=email,
        role=user.role,
    )


@app.post(
    f"{settings.api_prefix}/queue",
    response_model=QueueEntryResponse,
    status_code=201,
    tags=["queue"],
)
def create_queue_entry(
    entry: QueueEntryCreate,
    current_user: dict[str, str] = Depends(
        require_roles("patient", "reception")
    ),
) -> QueueEntryResponse:
    patient_email = (
        current_user["email"]
        if current_user["role"] == "patient"
        else entry.patient_email.strip().lower()
    )

    department = entry.department.strip()

    token_number = queue_collection.count_documents(
        {"department": department}
    ) + 1

    position = queue_collection.count_documents(
        {
            "department": department,
            "status": QueueStatus.WAITING.value,
        }
    ) + 1

    queue_document = {
        "token_number": token_number,
        "patient_email": patient_email,
        "department": department,
        "doctor_email": entry.doctor_email,
        "status": QueueStatus.WAITING.value,
    }

    queue_collection.insert_one(queue_document)

    return QueueEntryResponse(
        token_number=token_number,
        patient_email=patient_email,
        department=department,
        doctor_email=entry.doctor_email,
        status=QueueStatus.WAITING,
        position=position,
    )

@app.get(
    f"{settings.api_prefix}/queue/my",
    response_model=QueueEntryResponse,
    tags=["queue"],
)
def get_my_queue_entry(
    current_user: dict[str, str] = Depends(require_roles("patient")),
) -> QueueEntryResponse:
    queue_entry = queue_collection.find_one(
        {"patient_email": current_user["email"]},
        sort=[("_id", -1)],
    )

    if not queue_entry:
        raise HTTPException(
            status_code=404,
            detail="No queue entry found for this patient",
        )

    position = queue_collection.count_documents(
        {
            "department": queue_entry["department"],
            "status": QueueStatus.WAITING.value,
            "token_number": {
                "$lte": queue_entry["token_number"],
            },
        }
    )

    return QueueEntryResponse(
        token_number=queue_entry["token_number"],
        patient_email=queue_entry["patient_email"],
        department=queue_entry["department"],
        doctor_email=queue_entry.get("doctor_email"),
        status=QueueStatus(queue_entry["status"]),
        position=position,
    )
@app.patch(
    f"{settings.api_prefix}/queue/{{department}}/{{token_number}}/status",
    response_model=QueueEntryResponse,
    tags=["queue"],
)
def update_queue_status(
    department: str,
    token_number: int,
    update: QueueStatusUpdate,
    current_user: dict[str, str] = Depends(
        require_roles("doctor", "reception")
    ),
) -> QueueEntryResponse:
    queue_entry = queue_collection.find_one(
        {
            "department": department,
            "token_number": token_number,
        }
    )

    if not queue_entry:
        raise HTTPException(
            status_code=404,
            detail="Queue entry not found",
        )

    queue_collection.update_one(
        {"_id": queue_entry["_id"]},
        {"$set": {"status": update.status.value}},
    )

    position = queue_collection.count_documents(
        {
            "department": department,
            "status": QueueStatus.WAITING.value,
            "token_number": {
                "$lte": token_number,
            },
        }
    )

    return QueueEntryResponse(
        token_number=token_number,
        patient_email=queue_entry["patient_email"],
        department=queue_entry["department"],
        doctor_email=queue_entry.get("doctor_email"),
        status=update.status,
        position=position,
    )

@app.post(
    f"{settings.api_prefix}/queue/{{department}}/{{token_number}}/qr",
    response_model=QRTokenResponse,
    tags=["qr"],
)
def generate_queue_qr(
    department: str,
    token_number: int,
    current_user: dict[str, str] = Depends(
        require_roles("patient")
    ),
) -> QRTokenResponse:
    queue_entry = queue_collection.find_one(
        {
            "department": department,
            "token_number": token_number,
            "patient_email": current_user["email"],
        }
    )

    if not queue_entry:
        raise HTTPException(
            status_code=404,
            detail="Queue entry not found for this patient",
        )

    raw_token = generate_qr_token()
    token_hash = hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()

    created_at = datetime.now(timezone.utc)
    expires_at = created_at + timedelta(minutes=15)

    qr_tokens_collection.insert_one(
        {
            "token_hash": token_hash,
            "queue_entry_id": str(queue_entry["_id"]),
            "department": department,
            "token_number": token_number,
            "expires_at": expires_at,
            "created_at": created_at,
        }
    )

    return QRTokenResponse(
        qr_image_data=generate_qr_image_data(raw_token),
        expires_at=expires_at,
    )

@app.post(
    f"{settings.api_prefix}/qr/verify",
    response_model=QRVerificationResponse,
    tags=["qr"],
)
def verify_qr_token(
    request: QRVerificationRequest,
    current_user: dict[str, str] = Depends(
        require_roles("doctor", "reception")
    ),
) -> QRVerificationResponse:
    token_hash = hashlib.sha256(
        request.token.encode("utf-8")
    ).hexdigest()

    qr_record = qr_tokens_collection.find_one(
        {
            "token_hash": token_hash,
            "expires_at": {
                "$gt": datetime.now(timezone.utc),
            },
        }
    )

    if not qr_record:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired QR token",
        )

    queue_entry = queue_collection.find_one(
        {
            "department": qr_record["department"],
            "token_number": qr_record["token_number"],
        }
    )

    if not queue_entry:
        raise HTTPException(
            status_code=404,
            detail="Queue entry not found",
        )

    return QRVerificationResponse(
        valid=True,
        patient_email=queue_entry["patient_email"],
        department=queue_entry["department"],
        token_number=queue_entry["token_number"],
        status=queue_entry["status"],
    )