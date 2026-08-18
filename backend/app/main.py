from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient

from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    require_roles,
    verify_password,
)
from app.config import get_settings
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
    description="Foundation for the Smart QR-Based Hospital Patient Journey Management System.",
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
        "phase": "2",
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