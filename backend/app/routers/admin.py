from fastapi import APIRouter, Depends, HTTPException

from app.auth import hash_password, require_roles
from app.database import queue_collection, users_collection
from app.queue_schemas import QueueEntryResponse
from app.schemas import StaffUserCreate, UserResponse
from app.services.queue_service import (
    ACTIVE_STATUSES,
    get_priority_rank,
    queue_response,
)

router = APIRouter(prefix="/admin", tags=["administration"])


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=201,
)
@router.post(
    "/staff",
    response_model=UserResponse,
    status_code=201,
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

    user_doc = {
        "email": email,
        "password_hash": hash_password(user.password),
        "role": user.role.value,
    }
    if user.name and user.name.strip():
        user_doc["name"] = user.name.strip()
    if user.department and user.department.strip():
        user_doc["department"] = user.department.strip()

    users_collection.insert_one(user_doc)

    return UserResponse(
        email=email,
        role=user.role,
        name=user_doc.get("name"),
        department=user_doc.get("department"),
    )


@router.get(
    "/users",
    response_model=list[UserResponse],
)
def get_admin_users(
    current_user: dict[str, str] = Depends(require_roles("admin")),
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
            },
        )
    )

    return [
        UserResponse(
            email=user["email"],
            role=user["role"],
            name=user.get("name"),
            department=user.get("department"),
        )
        for user in users
    ]


@router.get(
    "/queue",
    response_model=list[QueueEntryResponse],
)
def get_admin_queue(
    current_user: dict[str, str] = Depends(require_roles("admin")),
) -> list[QueueEntryResponse]:
    entries = list(
        queue_collection.find(
            {},
            {
                "_id": 0,
            },
        )
    )

    entries.sort(
        key=lambda entry: (
            entry.get("department", ""),
            0 if entry.get("status") in ACTIVE_STATUSES else 1,
            get_priority_rank(entry)
            if entry.get("status") in ACTIVE_STATUSES
            else 999,
            (
                entry.get("position", 999999)
                if entry.get("position", 0) > 0
                else 999999
            ),
            entry.get("token_number", 999999),
        )
    )

    return [queue_response(entry) for entry in entries]
