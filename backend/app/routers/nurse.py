# ruff: noqa: B008
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_roles
from app.database import (
    nurse_assessments_collection,
    queue_collection,
    users_collection,
)
from app.queue_schemas import (
    NurseAssessmentCreate,
    NurseAssessmentResponse,
    QueueStatus,
    TriagePriority,
)
from app.services.queue_service import (
    ACTIVE_STATUSES,
    TRIAGE_STATUS,
    NurseDoctorAssignmentUpdate,
    NursePriorityUpdate,
    recalculate_queue_state,
)

router = APIRouter(prefix="/nurse", tags=["nurse"])


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


def ensure_doctor_account(doctor_email: str) -> str:
    normalized_email = doctor_email.strip().lower()

    doctor = users_collection.find_one(
        {
            "email": normalized_email,
            "role": "doctor",
        },
        {"_id": 1},
    )

    if not doctor:
        raise HTTPException(
            status_code=404,
            detail="Doctor account not found",
        )

    return normalized_email


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


# ============================================================
# NURSE - GET PATIENTS WAITING FOR TRIAGE
# ============================================================

@router.get("/patients")
def get_nurse_patients(
    current_user: dict[str, str] = Depends(require_roles("nurse")),
) -> list[dict[str, Any]]:
    entries = list(
        queue_collection.find(
            {"status": TRIAGE_STATUS},
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

    entries.sort(
        key=lambda item: (
            item.get("position", 999999),
            item.get("token_number", 999999),
        )
    )

    return entries


# ============================================================
# NURSE - CREATE ASSESSMENT
# ============================================================

@router.post(
    "/assessments",
    response_model=NurseAssessmentResponse,
    status_code=201,
)
async def create_nurse_assessment(
    assessment: NurseAssessmentCreate,
    current_user: dict[str, str] = Depends(require_roles("nurse")),
) -> NurseAssessmentResponse:
    patient_email = assessment.patient_email.strip().lower()
    department = assessment.department.strip()
    doctor_email = (
        assessment.doctor_email.strip().lower()
        if assessment.doctor_email
        else None
    )
    now = datetime.now(timezone.utc)

    queue_entry = queue_collection.find_one(
        {
            "patient_email": patient_email,
            "department": department,
            "status": TRIAGE_STATUS,
        },
        sort=[("_id", -1)],
    )

    if not queue_entry:
        raise HTTPException(
            status_code=404,
            detail="Patient is not waiting for nurse assessment",
        )

    document = {
        "patient_email": patient_email,
        "department": department,
        "doctor_email": doctor_email,
        "temperature": assessment.temperature,
        "pulse": assessment.pulse,
        "systolic_bp": assessment.systolic_bp,
        "diastolic_bp": assessment.diastolic_bp,
        "spo2": assessment.spo2,
        "pain_level": assessment.pain_level,
        "symptoms": assessment.symptoms,
        "nurse_notes": assessment.nurse_notes,
        "priority": assessment.priority.value,
        "nurse_email": current_user["email"],
        "created_at": now,
        "updated_at": now,
    }

    result = nurse_assessments_collection.insert_one(document)

    # Nurse assessment is completed.
    # The patient must now wait for Reception QR verification.
    # Do NOT move the patient directly into the doctor queue.
    queue_update: dict[str, Any] = {
        "status": QueueStatus.WAITING_FOR_RECEPTION.value,
        "priority": assessment.priority.value,
        "position": 0,
        "queue_access_verified": False,
        "updated_at": now,
    }

    if doctor_email:
        queue_update["doctor_email"] = doctor_email

    queue_collection.update_one(
        {"_id": queue_entry["_id"]},
        {"$set": queue_update},
    )

    await recalculate_queue_state(department)

    return NurseAssessmentResponse(
        id=str(result.inserted_id),
        patient_email=patient_email,
        department=department,
        doctor_email=doctor_email,
        temperature=assessment.temperature,
        pulse=assessment.pulse,
        systolic_bp=assessment.systolic_bp,
        diastolic_bp=assessment.diastolic_bp,
        spo2=assessment.spo2,
        pain_level=assessment.pain_level,
        symptoms=assessment.symptoms,
        nurse_notes=assessment.nurse_notes,
        priority=assessment.priority,
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
    )


# ============================================================
# NURSE - UPDATE TRIAGE PRIORITY
# ============================================================

@router.patch(
    "/assessments/{patient_email}/priority",
    response_model=NurseAssessmentResponse,
)
async def update_nurse_priority(
    patient_email: str,
    update: NursePriorityUpdate,
    current_user: dict[str, str] = Depends(require_roles("nurse")),
) -> NurseAssessmentResponse:
    patient_email = patient_email.strip().lower()

    document = nurse_assessments_collection.find_one(
        {"patient_email": patient_email},
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
        {"$set": {"priority": new_priority, "updated_at": now}},
    )

    queue_entry = get_latest_patient_queue_entry(patient_email, department)

    allowed_statuses = {TRIAGE_STATUS, *ACTIVE_STATUSES}
    if queue_entry["status"] not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail="Patient is not in a state where triage priority can be changed",
        )

    queue_collection.update_one(
        {"_id": queue_entry["_id"]},
        {"$set": {"priority": new_priority, "updated_at": now}},
    )

    await recalculate_queue_state(department)

    updated = nurse_assessments_collection.find_one({"_id": document["_id"]})
    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Updated nurse assessment not found",
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
        priority=TriagePriority(
            updated.get("priority", TriagePriority.NORMAL.value)
        ),
        created_at=updated["created_at"].isoformat(),
        updated_at=updated["updated_at"].isoformat(),
    )


# ============================================================
# NURSE - ASSIGN / CHANGE DOCTOR
# ============================================================

@router.patch(
    "/assessments/{patient_email}/doctor",
    response_model=NurseAssessmentResponse,
)
async def update_nurse_doctor_assignment(
    patient_email: str,
    update: NurseDoctorAssignmentUpdate,
    current_user: dict[str, str] = Depends(require_roles("nurse")),
) -> NurseAssessmentResponse:
    patient_email = patient_email.strip().lower()
    doctor_email = ensure_doctor_account(update.doctor_email)

    document = nurse_assessments_collection.find_one(
        {"patient_email": patient_email},
        sort=[("_id", -1)],
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="No nurse assessment found for this patient",
        )

    department = document["department"]
    queue_entry = get_latest_patient_queue_entry(patient_email, department)

    allowed_statuses = {TRIAGE_STATUS, *ACTIVE_STATUSES}
    if queue_entry["status"] not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail="Patient is not in a state where the doctor assignment can be changed",
        )

    now = datetime.now(timezone.utc)

    nurse_assessments_collection.update_one(
        {"_id": document["_id"]},
        {"$set": {"doctor_email": doctor_email, "updated_at": now}},
    )

    queue_update: dict[str, Any] = {
        "doctor_email": doctor_email,
        "updated_at": now,
    }

    if queue_entry["status"] == TRIAGE_STATUS:
        # Doctor assignment alone must NOT enter the doctor queue.
        # The patient must complete nurse assessment first and then
        # Reception QR verification before reaching WAITING.
        queue_update["status"] = QueueStatus.WAITING_FOR_RECEPTION.value
        queue_update["position"] = 0
        queue_update["queue_access_verified"] = False

    queue_collection.update_one(
        {"_id": queue_entry["_id"]},
        {"$set": queue_update},
    )

    await recalculate_queue_state(department)

    updated = nurse_assessments_collection.find_one({"_id": document["_id"]})
    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Nurse assessment not found after update",
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
        priority=TriagePriority(
            updated.get("priority", TriagePriority.NORMAL.value)
        ),
        created_at=updated["created_at"].isoformat(),
        updated_at=updated["updated_at"].isoformat(),
    )


# ============================================================
# NURSE / DOCTOR - GET ASSESSMENT
# ============================================================

@router.get(
    "/assessments/{patient_email}",
    response_model=NurseAssessmentResponse,
)
def get_nurse_assessment(
    patient_email: str,
    current_user: dict[str, str] = Depends(
        require_roles("nurse", "doctor")
    ),
) -> NurseAssessmentResponse:
    patient_email = patient_email.strip().lower()

    document = nurse_assessments_collection.find_one(
        {"patient_email": patient_email},
        sort=[("_id", -1)],
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="No nurse assessment found for this patient",
        )

    ensure_doctor_assessment_access(document, current_user)

    return NurseAssessmentResponse(
        id=str(document["_id"]),
        patient_email=document["patient_email"],
        department=document["department"],
        doctor_email=document.get("doctor_email"),
        temperature=document.get("temperature"),
        pulse=document.get("pulse"),
        systolic_bp=document.get("systolic_bp"),
        diastolic_bp=document.get("diastolic_bp"),
        spo2=document.get("spo2"),
        pain_level=document.get("pain_level"),
        symptoms=document.get("symptoms"),
        nurse_notes=document.get("nurse_notes"),
        priority=TriagePriority(
            document.get("priority", TriagePriority.NORMAL.value)
        ),
        created_at=document["created_at"].isoformat(),
        updated_at=document["updated_at"].isoformat(),
    )
