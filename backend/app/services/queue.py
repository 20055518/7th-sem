"""Queue business logic for Phase 2+.

Handles queue entry lifecycle: join, call-next, status updates,
prediction triggers, and WebSocket broadcast hooks. Keeps the routes
thin and testable."""
from typing import Optional
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models import (
    QueueEntry,
    QueueEntryCreate,
    QueueEntryUpdate,
    MLPrediction,
    MLPredictionCreate,
    Notification,
    NotificationCreate,
    SystemSettings,
)


async def join_queue(
    db: AsyncIOMotorDatabase,
    *,
    patient_id: str,
    doctor_id: str,
    department_id: str,
    token_number: str,
) -> QueueEntry:
    """Register a new patient queue entry and return the document."""
    now = datetime.utcnow()
    entry = QueueEntry(
        patientId=patient_id,
        doctorId=doctor_id,
        departmentId=department_id,
        tokenNumber=token_number,
        status="waiting",
        predictedWait=None,
        createdAt=now,
        updatedAt=now,
    )
    collection = db["queue_entries"]
    doc = entry.model_dump(exclude={"id"})
    result = await collection.insert_one(doc)
    created = await collection.find_one({"_id": result.inserted_id})
    # TODO: broadcast queue_updated WebSocket event
    return QueueEntry(**created)


async def call_next(
    db: AsyncIOMotorDatabase,
    *,
    doctor_id: str,
) -> Optional[QueueEntry]:
    """Transition the next waiting patient to 'called' status.

    Returns the promoted entry, or None if no waiting patients."""
    # 1. Find the first waiting entry for this doctor, ordered by position / createdAt
    collection = db["queue_entries"]
    next_entry_doc = await collection.find_one(
        {"doctorId": doctor_id, "status": "waiting"},
        sort=[("position", 1)],  # simplest: lowest position number first
    )
    if not next_entry_doc:
        return None

    entry_id = next_entry_doc["_id"]
    # 2. Mark this entry as called
    await collection.update_one(
        {"_id": entry_id},
        {
            "$set": {"status": "called", "updatedAt": datetime.utcnow()},
            "$unset": {"predictedWait": ""},  # clear stale prediction
        },
    )

    # 3. Recalculate waiting-time predictions for remaining queue
    #    (placeholder - Phase 8+ will invoke the DHQPM pipeline)
    await _recalculate_predictions(db, doctor_id=doctor_id)

    # 4. Broadcast queue_updated + patient_called WebSocket events
    # TODO: WebSocket broadcast

    # 5. Trigger "You're Next" notification if threshold reached
    # TODO: notification service

    # 6. Return the updated document
    return await collection.find_one({"_id": entry_id})


async def complete_consultation(
    db: AsyncIOMotorDatabase,
    *,
    queue_entry_id: str,
    doctor_id: str,
) -> Optional[QueueEntry]:
    """Mark a consultation as complete and advance the queue."""
    collection = db["queue_entries"]

    # 1. Find and mark the entry completed
    result = await collection.update_one(
        {"_id": queue_entry_id, "doctorId": doctor_id},
        {
            "$set": {
                "status": "completed",
                "updatedAt": datetime.utcnow(),
            },
        },
    )
    if result.modified_count == 0:
        return None

    # 2. Promote the next patient (if any)
    next_entry = await call_next(db=db, doctor_id=doctor_id)
    # 3. Record the consultation
    # TODO: consult collection insert
    # 4. Run DHQPM update + broadcast
    # TODO: WebSocket + prediction recalc
    return next_entry


async def _recalculate_predictions(
    db: AsyncIOMotorDatabase,
    *,
    doctor_id: str,
) -> None:
    """Placeholder: invoke the DHQPM pipeline for the doctor's queue.

    In Phase 8+ this will call the ML + Bayesian pipeline and update
    `predictedWait` on affected queue entries."""
    # For now: no-op. Will be wired to the ML/bayesian modules later.
    pass