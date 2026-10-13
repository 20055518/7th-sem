from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_roles
from app.database import doctor_consultations_collection, queue_collection
from app.queue_schemas import QueueEntryResponse, QueueStatus
from app.routers.queue import validate_doctor_status_transition
from app.services.queue_service import (
    ACTIVE_STATUSES,
    DoctorConsultationCreate,
    DoctorConsultationResponse,
    clear_prediction_fields,
    get_priority_rank,
    queue_response,
    recalculate_queue_state,
)

router = APIRouter(prefix="/doctor", tags=["doctor"])

doctor_required = Depends(require_roles("doctor"))


# ============================================================
# DOCTOR - DASHBOARD
# ============================================================

@router.get("/dashboard")
def get_doctor_dashboard(
    current_user: dict[str, str] = doctor_required,
) -> dict[str, Any]:
    doctor_email = current_user["email"].strip().lower()

    active_entries = list(
        queue_collection.find(
            {
                "doctor_email": doctor_email,
                "status": {"$in": list(ACTIVE_STATUSES)},
            },
            {"_id": 0},
        )
    )

    active_entries.sort(
        key=lambda entry: (
            get_priority_rank(entry),
            (
                entry.get("position", 999999)
                if entry.get("position", 0) > 0
                else 999999
            ),
            entry.get("token_number", 999999),
        )
    )

    skipped_entries = list(
        queue_collection.find(
            {
                "doctor_email": doctor_email,
                "status": QueueStatus.SKIPPED.value,
            },
            {"_id": 0},
        )
    )

    skipped_entries.sort(
        key=lambda entry: (
            entry.get("updated_at")
            or entry.get("created_at")
            or datetime.min.replace(tzinfo=timezone.utc),
            entry.get("token_number", 999999),
        ),
        reverse=True,
    )

    departments = sorted(
        {
            entry["department"]
            for entry in (active_entries + skipped_entries)
            if entry.get("department")
        }
    )

    active_patients = [queue_response(entry) for entry in active_entries]
    skipped_patients = [queue_response(entry) for entry in skipped_entries]

    return {
        "doctor_email": doctor_email,
        "departments": departments,
        "active_patient_count": len(active_patients),
        "skipped_patient_count": len(skipped_patients),
        "patients": active_patients + skipped_patients,
        "active_patients": active_patients,
        "skipped_patients": skipped_patients,
    }


# ============================================================
# DOCTOR - GET PATIENT
# ============================================================

@router.get(
    "/patients/{token_number}",
    response_model=QueueEntryResponse,
)
def get_doctor_patient(
    token_number: int,
    current_user: dict[str, str] = doctor_required,
) -> QueueEntryResponse:
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
            detail="Patient not found in your assigned queue",
        )

    return queue_response(queue_entry)


# ============================================================
# DOCTOR - CALL PATIENT
# ============================================================

@router.patch(
    "/patients/{token_number}/call",
    response_model=QueueEntryResponse,
)
async def doctor_call_patient(
    token_number: int,
    current_user: dict[str, str] = doctor_required,
) -> QueueEntryResponse:
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
    if queue_entry.get("queue_access_verified") is not True:
        raise HTTPException(
            status_code=400,
            detail="Patient must complete reception QR verification before being called",
        )

    # ----------------------------------------------------------
    # ONLY ONE ACTIVE PATIENT PER DOCTOR
    # ----------------------------------------------------------
    active_patient = queue_collection.find_one(
        {
            "doctor_email": doctor_email,
            "status": {
                "$in": [
                    QueueStatus.CALLED.value,
                    QueueStatus.IN_CONSULTATION.value,
                ]
            },
            "_id": {"$ne": queue_entry["_id"]},
        },
        sort=[("_id", -1)],
    )

    if active_patient:
        active_token = active_patient.get("token_number")

        if active_patient.get("status") == QueueStatus.IN_CONSULTATION.value:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Patient #{active_token:03d} is currently in consultation. "
                    "Complete that consultation before calling another patient."
                ),
            )

        raise HTTPException(
            status_code=409,
            detail=(
                f"Patient #{active_token:03d} has already been called. "
                "Start or finish that patient before calling another patient."
            ),
        )

    validate_doctor_status_transition(
        queue_entry["status"],
        QueueStatus.CALLED.value,
    )

    queue_collection.update_one(
        {"_id": queue_entry["_id"]},
        {
            "$set": {
                "status": QueueStatus.CALLED.value,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )

    await recalculate_queue_state(queue_entry["department"])

    updated = queue_collection.find_one({"_id": queue_entry["_id"]})
    if updated is None:
        raise HTTPException(
            status_code=500,
            detail="Failed to reload the updated patient record.",
        )
    return queue_response(updated)


# ============================================================
# DOCTOR - START CONSULTATION
# ============================================================

@router.patch(
    "/patients/{token_number}/start",
    response_model=QueueEntryResponse,
)
async def doctor_start_consultation(
    token_number: int,
    current_user: dict[str, str] = doctor_required,
) -> QueueEntryResponse:
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

    # ----------------------------------------------------------
    # ONLY ONE PATIENT CAN BE IN CONSULTATION
    # ----------------------------------------------------------
    existing_consultation = queue_collection.find_one(
        {
            "doctor_email": doctor_email,
            "status": QueueStatus.IN_CONSULTATION.value,
            "_id": {"$ne": queue_entry["_id"]},
        },
        sort=[("_id", -1)],
    )

    if existing_consultation:
        active_token = existing_consultation.get("token_number")
        raise HTTPException(
            status_code=409,
            detail=(
                f"Patient #{active_token:03d} is already in consultation. "
                "Complete that consultation before starting another patient."
            ),
        )

    validate_doctor_status_transition(
        queue_entry["status"],
        QueueStatus.IN_CONSULTATION.value,
    )

    now = datetime.now(timezone.utc)

    queue_collection.update_one(
        {"_id": queue_entry["_id"]},
        {
            "$set": {
                "status": QueueStatus.IN_CONSULTATION.value,
                "updated_at": now,
            }
        },
    )

    doctor_consultations_collection.update_one(
        {
            "queue_entry_id": str(queue_entry["_id"]),
            "doctor_email": doctor_email,
        },
        {
            "$setOnInsert": {
                "queue_entry_id": str(queue_entry["_id"]),
                "token_number": token_number,
                "patient_email": queue_entry["patient_email"],
                "department": queue_entry["department"],
                "doctor_email": doctor_email,
                "diagnosis": "",
                "consultation_notes": "",
                "prescription": "",
                "treatment_advice": "",
                "started_at": now,
                "completed_at": None,
                "created_at": now,
                "updated_at": now,
            }
        },
        upsert=True,
    )

    await recalculate_queue_state(queue_entry["department"])

    updated = queue_collection.find_one({"_id": queue_entry["_id"]})
    if updated is None:
        raise HTTPException(
            status_code=500,
            detail="Failed to reload the updated patient record.",
        )
    return queue_response(updated)


# ============================================================
# DOCTOR - GET CONSULTATION
# ============================================================

@router.get(
    "/patients/{token_number}/consultation",
    response_model=DoctorConsultationResponse,
)
def get_doctor_consultation(
    token_number: int,
    current_user: dict[str, str] = doctor_required,
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

@router.put(
    "/patients/{token_number}/consultation",
    response_model=DoctorConsultationResponse,
)
def save_doctor_consultation(
    token_number: int,
    consultation_data: DoctorConsultationCreate,
    current_user: dict[str, str] = doctor_required,
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

@router.patch(
    "/patients/{token_number}/complete",
    response_model=QueueEntryResponse,
)
async def doctor_complete_consultation(
    token_number: int,
    current_user: dict[str, str] = doctor_required,
) -> QueueEntryResponse:
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
        {
            "$set": {
                "status": QueueStatus.COMPLETED.value,
                "position": 0,
                "updated_at": now,
                **clear_prediction_fields(),
            }
        },
    )

    await recalculate_queue_state(queue_entry["department"])

    updated = queue_collection.find_one({"_id": queue_entry["_id"]})
    if updated is None:
        raise HTTPException(
            status_code=500,
            detail="Failed to reload the updated patient record.",
        )
    return queue_response(updated)
