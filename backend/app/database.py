import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pymongo import MongoClient

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Synchronous MongoDB Client
mongo_client = MongoClient(
    settings.mongodb_uri,
    serverSelectionTimeoutMS=2000,
)

database = mongo_client.get_database()

users_collection = database["users"]
queue_collection = database["queue_entries"]
qr_tokens_collection = database["qr_tokens"]
nurse_assessments_collection = database["nurse_assessments"]
doctor_consultations_collection = database["doctor_consultations"]


def ensure_database_indexes() -> None:
    """Create indexes used by the synchronous MongoDB schema."""
    users_collection.create_index("email", unique=True)
    queue_collection.create_index(
        [("department", 1), ("token_number", 1)],
        unique=True,
    )
    queue_collection.create_index(
        [("patient_email", 1), ("status", 1), ("created_at", -1)]
    )
    queue_collection.create_index(
        [("department", 1), ("status", 1), ("position", 1)]
    )
    qr_tokens_collection.create_index("token_hash", unique=True)
    qr_tokens_collection.create_index("expires_at", expireAfterSeconds=0)
    qr_tokens_collection.create_index("queue_entry_id")
    nurse_assessments_collection.create_index(
        [("patient_email", 1), ("department", 1), ("created_at", -1)]
    )
    doctor_consultations_collection.create_index("queue_entry_id", unique=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        mongo_client.admin.command("ping")
        ensure_database_indexes()
        logger.info("MongoDB connected and indexes verified")
    except Exception:
        # The health endpoint exposes this state without hiding it behind a
        # restart loop when the database temporarily is unavailable.
        logger.exception("MongoDB was unavailable during application startup")
    yield
    mongo_client.close()
