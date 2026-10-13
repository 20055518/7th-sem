"""Async MongoDB connection and client setup for Phase 2+."""

from motor.motor_asyncio import AsyncMongoClient
from pymongo import MongoClient

from app.config import get_settings

settings = get_settings()


def get_mongo_client() -> AsyncMongoClient:
    """Return an authenticated async MongoDB client."""
    return AsyncMongoClient(settings.mongodb_uri)


def get_sync_mongo_client() -> MongoClient:
    """Return a synchronous MongoDB client for setup / migration scripts."""
    return MongoClient(settings.mongodb_uri)


async def init_db(app=None) -> AsyncMongoClient:
    """Attach a database instance to the FastAPI app state.

    Usage: dependency injection via `request.app.state.db`.
    """
    client = get_mongo_client()
    db = client[settings.mongodb_uri.rsplit("/", 1)[-1]]

    # Ensure critical indexes for Phase 2
    # queue_entries: unique tokenNumber, patientId + createdAt, status + createdAt
    await db.queue_entries.create_index("tokenNumber", unique=True)
    await db.queue_entries.create_index([("patientId", 1), ("createdAt", -1)])
    await db.queue_entries.create_index([("doctorId", 1), ("status", 1), ("createdAt", -1)])
    await db.queue_entries.create_index([("departmentId", 1), ("status", 1), ("createdAt", -1)])
    await db.queue_entries.create_index([("status", 1), ("createdAt", -1)])

    # qr_tokens: unique tokenHash, queueEntryId, expiresAt TTL
    await db.qr_tokens.create_index("tokenHash", unique=True)
    await db.qr_tokens.create_index("queueEntryId")
    await db.qr_tokens.create_index("expiresAt", expireAfterSeconds=0)  # TTL index

    # notifications: recipientUserId + createdAt, readAt
    await db.notifications.create_index([("recipientUserId", 1), ("createdAt", -1)])
    await db.notifications.create_index([("recipientUserId", 1), ("readAt", 1)])

    # audit_logs: userId + timestamp
    await db.audit_logs.create_index([("userId", 1), ("timestamp", -1)])

    # hospital_routes: unique departmentId + roomId
    await db.hospital_routes.create_index([("departmentId", 1), ("roomId", 1)], unique=True)

    # users: unique email, role
    await db.users.create_index("email", unique=True)
    await db.users.create_index("role")

    # doctors: userId (unique), departmentId
    await db.doctors.create_index("userId", unique=True)
    await db.doctors.create_index("departmentId")

    # patients: userId
    await db.patients.create_index("userId")

    # system_settings: singleton-ish via _id
    await db.system_settings.create_index("_id", unique=True)

    # ml_predictions: queueEntryId + createdAt
    await db.ml_predictions.create_index("queueEntryId")

    # consultations: queueEntryId (unique), doctorId + startedAt
    await db.consultations.create_index("queueEntryId", unique=True)
    await db.consultations.create_index("doctorId")

    # departments
    await db.departments.create_index("departmentId", unique=True)

    # rooms
    await db.rooms.create_index("roomId", unique=True)

    # rooms compound index
    await db.rooms.create_index([("departmentId", 1), ("roomId", 1)], unique=True)

    # If the app is passed, store the client reference for graceful shutdown
    if app is not None:
        app.state.mongo_client = client

    return client


async def close_db(app=None) -> None:
    """Close the MongoDB client connection."""
    if app is not None and hasattr(app.state, "mongo_client"):
        client = app.state.mongo_client
        client.close()
    elif hasattr(get_mongo_client(), "close"):
        get_mongo_client().close()