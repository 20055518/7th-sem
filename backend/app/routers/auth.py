from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    require_roles,
    verify_password,
)
from app.database import users_collection
from app.rate_limiter import client_address, login_limiter
from app.schemas import UserCreate, UserLogin, UserResponse

router = APIRouter(tags=["authentication"])


@router.post(
    "/auth/register",
    response_model=UserResponse,
    status_code=201,
)
def register_patient(
    user: UserCreate,
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
            "role": "patient",
        }
    )

    return UserResponse(
        email=email,
        role="patient",
    )


@router.post("/auth/login")
def login_user(
    user: UserLogin,
    request: Request,
) -> dict[str, str]:
    email = user.email.strip().lower()
    login_key = f"{client_address(request)}:{email}"
    login_limiter.check(login_key)

    stored_user = users_collection.find_one({"email": email})

    if not stored_user or not verify_password(
        user.password,
        stored_user["password_hash"],
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    login_limiter.clear(login_key)

    access_token = create_access_token(
        subject=email,
        role=stored_user["role"],
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": stored_user["role"],
    }


@router.get("/auth/me")
def get_logged_in_user(
    current_user: dict[str, str] = Depends(get_current_user),
) -> dict[str, str]:
    return current_user


@router.get(
    "/patient-area",
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
