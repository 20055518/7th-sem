from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_roles
from app.database import queue_collection, users_collection
from app.queue_schemas import (
    PublicQueueEntryResponse,
    QueueEntryCreate,
    QueueEntryResponse,
    QueueStatus,
    QueueStatusUpdate,
    TriagePriority,
)
from app.services.queue_service import (
    ACTIVE_STATUSES,
    TRIAGE_STATUS,
    RISK_MODEL_VERSION,
    clear_prediction_fields,
    get_priority_rank,
    queue_response,
    recalculate_queue_state,
)

router = APIRouter(tags=["queue"])


# ============================================================
# DOCTOR ACCESS CONTROL HELPERS
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
        {
            "department": department,
            "doctor_email": doctor_email,
        },
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
            detail=f"Invalid doctor status transition: {current_status} -> {new_status}",
        )


# ============================================================
# PATIENT - AVAILABLE DOCTORS
# ============================================================

@router.get(
    "/doctors/{department}",
    tags=["doctors"],
)
@router.get(
    "/patients/available-doctors",
    tags=["doctors"],
)
def get_available_doctors(
    department: str,
    current_user: dict[str, str] = Depends(require_roles("patient")),
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
            },
        )
    )

    result: list[dict[str, Any]] = []

    for doctor in doctors:
        email = (doctor.get("email") or "").strip().lower()
        if not email:
            continue

        active_patient = queue_collection.find_one(
            {
                "doctor_email": email,
                "status": {"$in": list(ACTIVE_STATUSES)},
            },
            {"_id": 1},
        )

        result.append(
            {
                "email": email,
                "name": doctor.get("name") or email,
                "department": doctor.get("department") or department,
                "available": active_patient is None,
            }
        )

    result.sort(
        key=lambda d: (
            not d["available"],
            d["name"].lower(),
        )
    )

    return result


# ============================================================
# JOIN QUEUE
# ============================================================

@router.post(
    "/queue",
    response_model=QueueEntryResponse,
    status_code=201,
)
@router.post(
    "/queue/join",
    response_model=QueueEntryResponse,
    status_code=201,
)
async def create_queue_entry(
    entry: QueueEntryCreate,
    current_user: dict[str, str] = Depends(
        require_roles("patient", "reception")
    ),
) -> QueueEntryResponse:
    patient_email = (
        current_user["email"]
        if current_user["role"] == "patient"
        else (entry.patient_email or "").strip().lower()
    )

    department = (entry.department or "").strip()

    existing_entry = queue_collection.find_one(
        {
            "patient_email": patient_email,
            "status": {
                "$in": [
                    TRIAGE_STATUS,
                    *ACTIVE_STATUSES,
                ]
            },
        }
    )

    if existing_entry:
        raise HTTPException(
            status_code=409,
            detail="Patient already has an active queue entry",
        )

    triage_count = queue_collection.count_documents(
        {
            "department": department,
            "status": TRIAGE_STATUS,
        }
    )

    last_entry = queue_collection.find_one(
        {"department": department},
        sort=[("token_number", -1)],
    )

    next_token = (
        last_entry.get("token_number", 0) + 1 if last_entry else 1
    )

    queue_document = {
        "token_number": next_token,
        "patient_email": patient_email,
        "department": department,
        "doctor_email": entry.doctor_email,
        "status": TRIAGE_STATUS,
        "position": triage_count + 1,
        "priority": TriagePriority.NORMAL.value,
        "queue_access_verified": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    result = queue_collection.insert_one(queue_document)
    created = queue_collection.find_one({"_id": result.inserted_id})

    if not created:
        raise HTTPException(
            status_code=500,
            detail="Queue entry was not created",
        )

    return queue_response(created)


# ============================================================
# GET MY QUEUE
# ============================================================

@router.get(
    "/queue/my",
    response_model=QueueEntryResponse,
)
def get_my_queue_entry(
    current_user: dict[str, str] = Depends(require_roles("patient")),
) -> QueueEntryResponse:
    patient_email = current_user["email"].strip().lower()

    queue_entry = queue_collection.find_one(
        {
            "patient_email": patient_email,
            "status": {
                "$in": [
                    TRIAGE_STATUS,
                    *ACTIVE_STATUSES,
                    QueueStatus.SKIPPED.value,
                ]
            },
        },
        sort=[("_id", -1)],
    )

    if not queue_entry:
        raise HTTPException(
            status_code=404,
            detail="No queue entry found for this patient",
        )

    return queue_response(queue_entry)


# ============================================================
# DEPARTMENT QUEUE (RECEPTION & DOCTOR)
# ============================================================

@router.get(
    "/queue/{department}",
    response_model=list[QueueEntryResponse],
)
async def get_department_queue(
    department: str,
    current_user: dict[str, str] = Depends(
        require_roles("doctor", "reception")
    ),
) -> list[QueueEntryResponse]:
    department = department.strip()
    if not department:
        raise HTTPException(
            status_code=400,
            detail="Department is required",
        )

    ensure_doctor_department_access(department, current_user)

    queue_filter: dict[str, Any] = {
        "department": department,
        "status": {
            "$in": [
                QueueStatus.WAITING.value,
                QueueStatus.CALLED.value,
                QueueStatus.IN_CONSULTATION.value,
                QueueStatus.SKIPPED.value,
            ]
        },
    }

    if current_user["role"] == "doctor":
        queue_filter["doctor_email"] = (
            current_user["email"].strip().lower()
        )

    entries = list(queue_collection.find(queue_filter))

    stale_risk = any(
        entry.get("status") == QueueStatus.WAITING.value
        and (
            not entry.get("risk_level")
            or entry.get("risk_model_version") != RISK_MODEL_VERSION
        )
        for entry in entries
    )

    if stale_risk:
        await recalculate_queue_state(department)
        entries = list(queue_collection.find(queue_filter))

    entries.sort(
        key=lambda entry: (
            0 if entry["status"] in ACTIVE_STATUSES else 1,
            get_priority_rank(entry)
            if entry["status"] in ACTIVE_STATUSES
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


# ============================================================
# PUBLIC DEPARTMENT QUEUE
# ============================================================

@router.get(
    "/queue/{department}/public",
    response_model=list[PublicQueueEntryResponse],
)
@router.get(
    "/queue/public/{department}",
    response_model=list[PublicQueueEntryResponse],
)
def get_public_department_queue(
    department: str,
    current_user: dict[str, str] = Depends(require_roles("patient")),
) -> list[PublicQueueEntryResponse]:
    department = department.strip()

    entries = list(
        queue_collection.find(
            {
                "department": department,
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
# UPDATE QUEUE STATUS
# ============================================================

@router.patch(
    "/queue/{department}/{token_number}/status",
    response_model=QueueEntryResponse,
)
async def update_queue_status(
    department: str,
    token_number: int,
    update: QueueStatusUpdate,
    current_user: dict[str, str] = Depends(
        require_roles("doctor", "reception")
    ),
) -> QueueEntryResponse:
    department = department.strip()

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

    ensure_doctor_queue_entry_access(queue_entry, current_user)

    if queue_entry["status"] == TRIAGE_STATUS and update.status.value in {
        QueueStatus.CALLED.value,
        QueueStatus.IN_CONSULTATION.value,
        QueueStatus.COMPLETED.value,
    }:
        raise HTTPException(
            status_code=400,
            detail="Patient must complete nurse assessment before entering the doctor queue",
        )

    # Patient must scan the reception QR before entering doctor queue.
    # The only normal path to WAITING is successful QR verification.
    if (
        update.status.value == QueueStatus.WAITING.value
        and queue_entry.get("queue_access_verified") is not True
    ):
        raise HTTPException(
            status_code=400,
            detail="Patient must scan the reception QR before entering the doctor queue",
        )

    if current_user["role"] == "doctor":
        validate_doctor_status_transition(
            queue_entry["status"],
            update.status.value,
        )

    queue_collection.update_one(
        {"_id": queue_entry["_id"]},
        {
            "$set": {
                "status": update.status.value,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )

    if update.status.value not in ACTIVE_STATUSES:
        queue_collection.update_one(
            {"_id": queue_entry["_id"]},
            {
                "$set": {
                    "position": 0,
                    **clear_prediction_fields(),
                }
            },
        )

    await recalculate_queue_state(department)

    updated = queue_collection.find_one({"_id": queue_entry["_id"]})
    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Queue entry not found after update",
        )

    return queue_response(updated)


# ============================================================
# SKIP PATIENT
# ============================================================

@router.patch(
    "/queue/{department}/{token_number}/skip",
    response_model=QueueEntryResponse,
)
async def skip_queue_patient(
    department: str,
    token_number: int,
    current_user: dict[str, str] = Depends(
        require_roles("doctor", "reception")
    ),
) -> QueueEntryResponse:
    department = department.strip()

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

    ensure_doctor_queue_entry_access(queue_entry, current_user)

    if queue_entry["status"] not in {
        QueueStatus.WAITING.value,
        QueueStatus.CALLED.value,
    }:
        raise HTTPException(
            status_code=400,
            detail="Only waiting or called patients can be skipped",
        )

    queue_collection.update_one(
        {"_id": queue_entry["_id"]},
        {
            "$set": {
                "status": QueueStatus.SKIPPED.value,
                "position": 0,
                "updated_at": datetime.now(timezone.utc),
                **clear_prediction_fields(),
            }
        },
    )

    await recalculate_queue_state(department)

    updated = queue_collection.find_one({"_id": queue_entry["_id"]})
    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Queue entry not found after skip",
        )

    return queue_response(updated)


# ============================================================
# REQUEUE SKIPPED PATIENT
# ============================================================

@router.patch(
    "/queue/{department}/{token_number}/requeue",
    response_model=QueueEntryResponse,
)
async def requeue_queue_patient(
    department: str,
    token_number: int,
    current_user: dict[str, str] = Depends(
        require_roles("doctor", "reception")
    ),
) -> QueueEntryResponse:
    department = department.strip()

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

    ensure_doctor_queue_entry_access(queue_entry, current_user)

    if queue_entry["status"] != QueueStatus.SKIPPED.value:
        raise HTTPException(
            status_code=400,
            detail="Only skipped patients can be requeued",
        )

    # A skipped patient may return to the doctor queue only if
    # the patient had previously completed reception QR verification.
    if queue_entry.get("queue_access_verified") is not True:
        raise HTTPException(
            status_code=400,
            detail="Patient must scan the reception QR before being requeued",
        )

    active_count = queue_collection.count_documents(
        {
            "department": department,
            "status": {"$in": list(ACTIVE_STATUSES)},
        }
    )

    queue_collection.update_one(
        {"_id": queue_entry["_id"]},
        {
            "$set": {
                "status": QueueStatus.WAITING.value,
                "position": active_count + 1,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )

    await recalculate_queue_state(department)

    updated = queue_collection.find_one({"_id": queue_entry["_id"]})
    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Queue entry not found after requeue",
        )

    return queue_response(updated)
