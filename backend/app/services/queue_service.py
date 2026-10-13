import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.database import queue_collection
from app.queue_schemas import (
    QueueEntryResponse,
    QueueStatus,
    TriagePriority,
)
from app.services.ml_client import predict_waiting_time

logger = logging.getLogger(__name__)


# ============================================================
# ACTIVE DOCTOR QUEUE STATUSES & CONSTANTS
# ============================================================

ACTIVE_STATUSES = {
    QueueStatus.WAITING.value,
    QueueStatus.CALLED.value,
    QueueStatus.IN_CONSULTATION.value,
}

TRIAGE_STATUS = QueueStatus.WAITING_FOR_TRIAGE.value

PRIORITY_ORDER = {
    TriagePriority.URGENT.value: 1,
    TriagePriority.HIGH.value: 2,
    TriagePriority.MEDIUM.value: 3,
    TriagePriority.NORMAL.value: 4,
}

RISK_MODEL_VERSION = 2


# ============================================================
# NURSE UPDATE REQUEST SCHEMAS
# ============================================================

class NursePriorityUpdate(BaseModel):
    priority: TriagePriority


class NurseDoctorAssignmentUpdate(BaseModel):
    doctor_email: str = Field(
        min_length=5,
        max_length=254,
    )


# ============================================================
# DOCTOR CONSULTATION SCHEMAS
# ============================================================

class DoctorConsultationCreate(BaseModel):
    diagnosis: str = Field(
        default="",
        max_length=4000,
    )

    consultation_notes: str = Field(
        default="",
        max_length=6000,
    )

    prescription: str = Field(
        default="",
        max_length=6000,
    )

    treatment_advice: str = Field(
        default="",
        max_length=6000,
    )


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

    now = datetime.now(timezone.utc)

    if queue_length <= 5:
        queue_congestion = 0.20
    elif queue_length <= 10:
        queue_congestion = 0.45
    elif queue_length <= 20:
        queue_congestion = 0.70
    else:
        queue_congestion = 0.90

    normalized_priority = str(priority).strip().lower()

    if normalized_priority not in PRIORITY_ORDER:
        normalized_priority = TriagePriority.NORMAL.value

    ml_input = {
        "time_step": 0,
        "queue_congestion": queue_congestion,
        "patients_ahead": max(position - 1, 0),
        "queue_length": queue_length,
        "doctor_available": 1,
        "doctor_delay_minutes": 0,
        "average_consultation_minutes": 15,
        "completed_patients": 0,
        "historical_average_wait": 30,
        "historical_queue_length": 10,
        "arrival_hour": now.hour,
        "no_show_probability": 0.10,
        "doctor_id": doctor_email or "UNKNOWN",
        "department": department,
        "patient_type": "Regular",
        "priority_level": normalized_priority.title(),
        "appointment_type": "Walk-in",
        "day_of_week": now.strftime("%A"),
    }

    return await predict_waiting_time(ml_input)


# ============================================================
# RISK HELPERS
# ============================================================

def normalize_risk_value(value: Any) -> str:
    risk = str(value or "").strip().lower()

    if risk in {"urgent", "critical", "emergency"}:
        return "urgent"
    if risk in {"high", "severe"}:
        return "high"
    if risk in {"medium", "moderate"}:
        return "medium"
    if risk == "low":
        return "low"

    return ""


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if number != number:
            return default
        return number
    except (TypeError, ValueError):
        return default


def calculate_final_risk(
    prediction: dict[str, Any],
    priority: str = TriagePriority.NORMAL.value,
    position: int = 1,
    queue_length: int = 1,
) -> str:
    risk_scores = {
        "low": 0.10,
        "medium": 0.40,
        "high": 0.70,
        "urgent": 0.95,
    }

    ml_risk = normalize_risk_value(prediction.get("risk_level"))
    ml_score = risk_scores.get(ml_risk, 0.10)

    probability_long_or_more = max(
        0.0,
        min(1.0, safe_float(prediction.get("probability_long_or_more"))),
    )

    predicted_wait = max(0.0, safe_float(prediction.get("predicted_wait_minutes")))
    bayesian_wait = max(
        0.0, safe_float(prediction.get("bayesian_expected_wait_minutes"))
    )

    wait_minutes = min(max(predicted_wait, bayesian_wait), 90.0)
    wait_score = wait_minutes / 90.0

    normalized_priority = str(priority or TriagePriority.NORMAL.value).strip().lower()

    priority_scores = {
        TriagePriority.NORMAL.value: 0.10,
        TriagePriority.MEDIUM.value: 0.40,
        TriagePriority.HIGH.value: 0.70,
        TriagePriority.URGENT.value: 0.95,
    }
    priority_score = priority_scores.get(normalized_priority, 0.10)

    safe_position = max(int(position or 1), 1)
    safe_queue_length = max(int(queue_length or 1), 1)

    if safe_queue_length <= 1:
        queue_pressure = 0.0
    else:
        queue_pressure = min(
            max((safe_position - 1) / (safe_queue_length - 1), 0.0), 1.0
        )

    score = (
        0.35 * ml_score
        + 0.15 * probability_long_or_more
        + 0.10 * wait_score
        + 0.10 * priority_score
        + 0.30 * queue_pressure
    )

    score = max(score, priority_score)

    if score >= 0.80:
        return "urgent"
    if score >= 0.55:
        return "high"
    if score >= 0.28:
        return "medium"

    return "low"


def prediction_fields(
    prediction: dict[str, Any],
    priority: str = TriagePriority.NORMAL.value,
    position: int = 1,
    queue_length: int = 1,
) -> dict[str, Any]:
    return {
        "predicted_wait_minutes": prediction.get("predicted_wait_minutes"),
        "probability_short": prediction.get("probability_short"),
        "probability_moderate": prediction.get("probability_moderate"),
        "probability_long": prediction.get("probability_long"),
        "probability_very_long": prediction.get("probability_very_long"),
        "probability_long_or_more": prediction.get("probability_long_or_more"),
        "bayesian_state": prediction.get("bayesian_state"),
        "bayesian_expected_wait_minutes": prediction.get(
            "bayesian_expected_wait_minutes"
        ),
        "risk_level": calculate_final_risk(
            prediction,
            priority=priority,
            position=position,
            queue_length=queue_length,
        ),
        "risk_model_version": RISK_MODEL_VERSION,
    }


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
        "risk_model_version": None,
    }


def get_priority_rank(entry: dict[str, Any]) -> int:
    priority = (
        entry.get("priority", TriagePriority.NORMAL.value)
        or TriagePriority.NORMAL.value
    )
    priority = str(priority).strip().lower()
    return PRIORITY_ORDER.get(priority, PRIORITY_ORDER[TriagePriority.NORMAL.value])


# ============================================================
# REBUILD DOCTOR QUEUE WITH GRACEFUL ML FALLBACK
# ============================================================

async def recalculate_queue_state(department: str) -> None:
    department = department.strip()

    active_entries = list(
        queue_collection.find(
            {
                "department": department,
                "status": {"$in": list(ACTIVE_STATUSES)},
            }
        )
    )

    active_entries.sort(
        key=lambda entry: (
            get_priority_rank(entry),
            (
                entry.get("position", 999999)
                if isinstance(entry.get("position"), int)
                and entry.get("position", 0) > 0
                else 999999
            ),
            entry.get("token_number", 999999),
        )
    )

    for index, entry in enumerate(active_entries, start=1):
        queue_collection.update_one(
            {"_id": entry["_id"]},
            {
                "$set": {
                    "position": index,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

    queue_collection.update_many(
        {
            "department": department,
            "status": QueueStatus.SKIPPED.value,
        },
        {
            "$set": {
                "position": 0,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )

    queue_length = len(active_entries)

    for index, entry in enumerate(active_entries, start=1):
        if entry["status"] != QueueStatus.WAITING.value:
            continue

        try:
            prediction = await build_ml_prediction(
                department=department,
                doctor_email=entry.get("doctor_email"),
                position=index,
                queue_length=queue_length,
                priority=entry.get("priority", TriagePriority.NORMAL.value),
            )
        except Exception as error:
            # Resilient fallback when ML service is offline or unavailable
            logger.warning(
                "ML prediction service unavailable (%s). Using queue heuristic fallback.",
                error,
            )
            fallback_wait = max((index - 1) * 15.0, 0.0)
            prediction = {
                "predicted_wait_minutes": fallback_wait,
                "probability_short": 0.8 if fallback_wait <= 15 else 0.1,
                "probability_moderate": 0.8 if 15 < fallback_wait <= 30 else 0.2,
                "probability_long": 0.8 if 30 < fallback_wait <= 60 else 0.1,
                "probability_very_long": 0.8 if fallback_wait > 60 else 0.05,
                "probability_long_or_more": 0.85 if fallback_wait > 30 else 0.15,
                "bayesian_state": (
                    "Short"
                    if fallback_wait <= 15
                    else (
                        "Moderate"
                        if fallback_wait <= 30
                        else ("Long" if fallback_wait <= 60 else "Very Long")
                    )
                ),
                "bayesian_expected_wait_minutes": fallback_wait,
                "risk_level": (
                    "low"
                    if fallback_wait <= 15
                    else ("medium" if fallback_wait <= 30 else "high")
                ),
            }

        queue_collection.update_one(
            {"_id": entry["_id"]},
            {
                "$set": {
                    **prediction_fields(
                        prediction,
                        priority=entry.get(
                            "priority", TriagePriority.NORMAL.value
                        ),
                        position=index,
                        queue_length=queue_length,
                    ),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )


# ============================================================
# PRIVATE QUEUE RESPONSE HELPER
# ============================================================

def queue_response(entry: dict) -> QueueEntryResponse:
    return QueueEntryResponse(
        token_number=entry["token_number"],
        patient_email=entry["patient_email"],
        department=entry["department"],
        doctor_email=entry.get("doctor_email"),
        status=QueueStatus(entry["status"]),
        position=entry.get("position", 0),
        queue_access_verified=bool(entry.get("queue_access_verified", False)),
        priority=TriagePriority(
            entry.get("priority", TriagePriority.NORMAL.value)
        ),
        predicted_wait_minutes=entry.get("predicted_wait_minutes"),
        probability_short=entry.get("probability_short"),
        probability_moderate=entry.get("probability_moderate"),
        probability_long=entry.get("probability_long"),
        probability_very_long=entry.get("probability_very_long"),
        probability_long_or_more=entry.get("probability_long_or_more"),
        bayesian_state=entry.get("bayesian_state"),
        bayesian_expected_wait_minutes=entry.get(
            "bayesian_expected_wait_minutes"
        ),
        risk_level=entry.get("risk_level"),
    )
