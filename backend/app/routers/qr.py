import hashlib
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_roles
from app.database import qr_tokens_collection, queue_collection
from app.qr import generate_qr_image_data, generate_qr_token
from app.qr_schemas import (
    QRTokenResponse,
    QRVerificationRequest,
    QRVerificationResponse,
)
from app.queue_schemas import QueueStatus
from app.rate_limiter import limit_qr_verification
from app.services.queue_service import recalculate_queue_state


router = APIRouter(tags=["qr"])


ADMIN_RECEPTION_DEPENDS = Depends(
    require_roles("admin", "reception")
)
PATIENT_DEPENDS = Depends(require_roles("patient"))
QR_VERIFICATION_RATE_LIMIT_DEPENDS = Depends(
    limit_qr_verification
)


# ============================================================
# GENERATE QUEUE QR
#
# Reception generates the QR ONLY when:
#
# WAITING_FOR_RECEPTION
#
# Patient has NOT entered doctor queue yet.
# ============================================================

@router.post(
    "/queue/{department}/{token_number}/qr",
    response_model=QRTokenResponse,
)
def generate_queue_qr(
    department: str,
    token_number: int,
    current_user: dict[str, str] = ADMIN_RECEPTION_DEPENDS,
) -> QRTokenResponse:

    department = department.strip()


    # --------------------------------------------------------
    # FIND QUEUE ENTRY
    # --------------------------------------------------------

    queue_entry = queue_collection.find_one(
        {
            "department": department,
            "token_number": token_number,
        },
        sort=[("_id", -1)],
    )


    if not queue_entry:

        raise HTTPException(
            status_code=404,
            detail="Queue entry not found",
        )


    # --------------------------------------------------------
    # QR ONLY BEFORE DOCTOR-QUEUE ACCESS
    # --------------------------------------------------------
    # Normal state: WAITING_FOR_RECEPTION.
    #
    # Legacy repair: some older records may still contain
    # status=WAITING while queue_access_verified is false. Such a
    # record is NOT actually allowed in the doctor queue, so we
    # normalize it back to WAITING_FOR_RECEPTION here before issuing
    # the reception QR.
    # --------------------------------------------------------

    queue_status = queue_entry.get("status")
    queue_verified = queue_entry.get("queue_access_verified") is True

    if queue_verified:
        raise HTTPException(
            status_code=400,
            detail=(
                "Patient has already scanned the reception QR"
            ),
        )

    if queue_status == QueueStatus.WAITING.value:
        queue_collection.update_one(
            {
                "_id": queue_entry["_id"],
                "status": QueueStatus.WAITING.value,
                "queue_access_verified": {"$ne": True},
            },
            {
                "$set": {
                    "status": QueueStatus.WAITING_FOR_RECEPTION.value,
                    "position": 0,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

        queue_entry = queue_collection.find_one(
            {"_id": queue_entry["_id"]}
        )

    if not queue_entry or queue_entry.get("status") != QueueStatus.WAITING_FOR_RECEPTION.value:
        raise HTTPException(
            status_code=400,
            detail=(
                "QR can only be generated for patients "
                "waiting for reception"
            ),
        )


    # --------------------------------------------------------
    # GENERATE SECURE QR TOKEN
    # --------------------------------------------------------

    raw_token = generate_qr_token()


    # Store only the hash in MongoDB.
    token_hash = hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()


    # --------------------------------------------------------
    # QR EXPIRATION
    # --------------------------------------------------------

    created_at = datetime.now(
        timezone.utc
    )

    expires_at = (
        created_at
        + timedelta(minutes=15)
    )


    # --------------------------------------------------------
    # SAVE QR TOKEN
    # --------------------------------------------------------

    qr_tokens_collection.insert_one(
        {
            "token_hash": token_hash,

            "queue_entry_id":
                str(queue_entry["_id"]),

            "department":
                department,

            "token_number":
                token_number,

            "expires_at":
                expires_at,

            "created_at":
                created_at,

            "created_by":
                current_user["email"],

            "created_by_role":
                current_user["role"],
        }
    )


    # --------------------------------------------------------
    # GENERATE QR IMAGE
    # --------------------------------------------------------

    qr_image_data = generate_qr_image_data(
        raw_token
    )


    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    return QRTokenResponse(
    qr_image_data=generate_qr_image_data(raw_token),
    verification_code=raw_token,
    manual_code=manual_code,
    expires_at=expires_at,
)


# ============================================================
# VERIFY / SCAN RECEPTION QR
#
# REQUIRED FLOW:
#
# WAITING_FOR_RECEPTION
#          ↓
# Patient scans QR
#          ↓
# Verify QR
#          ↓
# queue_access_verified = True
#          ↓
# status = WAITING
#          ↓
# Recalculate doctor queue
#          ↓
# ML prediction
#          ↓
# Bayesian/risk calculation
# ============================================================

@router.post(
    "/qr/verify",
    response_model=QRVerificationResponse,
)
async def verify_qr_token(
    request: QRVerificationRequest,

    current_user: dict[str, str] = Depends(
        require_roles("patient")
    ),

    _: None = Depends(
        limit_qr_verification
    ),
) -> QRVerificationResponse:


    # --------------------------------------------------------
# VERIFY USING QR TOKEN OR MANUAL CODE
# --------------------------------------------------------

provided_token = (request.token or "").strip()
provided_code = (request.manual_code or "").strip()

if not provided_token and not provided_code:
    raise HTTPException(
        status_code=400,
        detail="QR token or manual verification code is required",
    )

now = datetime.now(timezone.utc)

if provided_code:
    # Manual code must be exactly 6 digits
    if not provided_code.isdigit() or len(provided_code) != 6:
        raise HTTPException(
            status_code=400,
            detail="Manual verification code must be 6 digits",
        )

    code_hash = hashlib.sha256(
        provided_code.encode("utf-8")
    ).hexdigest()

    qr_record = qr_tokens_collection.find_one(
        {
            "manual_code_hash": code_hash,
            "expires_at": {"$gt": now},
            "used_at": {"$exists": False},
        }
    )

else:
    token_hash = hashlib.sha256(
        provided_token.encode("utf-8")
    ).hexdigest()

    qr_record = qr_tokens_collection.find_one(
        {
            "token_hash": token_hash,
            "expires_at": {"$gt": now},
            "used_at": {"$exists": False},
        }
    )


    if not qr_record:

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired QR token",
        )


    # --------------------------------------------------------
    # GET QUEUE ENTRY ID
    # --------------------------------------------------------

    try:

        queue_entry_id = ObjectId(
            qr_record["queue_entry_id"]
        )

    except Exception:

        raise HTTPException(
            status_code=400,
            detail="Invalid QR queue reference",
        )


    # --------------------------------------------------------
    # FIND QUEUE ENTRY
    # --------------------------------------------------------

    queue_entry = queue_collection.find_one(
        {
            "_id":
                queue_entry_id
        }
    )


    if not queue_entry:

        raise HTTPException(
            status_code=404,
            detail="Queue entry not found",
        )


    # --------------------------------------------------------
    # VERIFY PATIENT
    # --------------------------------------------------------

    logged_in_patient = (
        current_user["email"]
        .strip()
        .lower()
    )


    qr_patient = (
        queue_entry["patient_email"]
        .strip()
        .lower()
    )


    if logged_in_patient != qr_patient:

        raise HTTPException(
            status_code=403,
            detail=(
                "This QR code does not belong "
                "to the logged-in patient"
            ),
        )


    # --------------------------------------------------------
    # PATIENT MUST STILL BE WAITING FOR RECEPTION
    # --------------------------------------------------------

    if (
        queue_entry.get("status")
        != QueueStatus.WAITING_FOR_RECEPTION.value
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "This patient is not currently "
                "waiting for reception"
            ),
        )


    # --------------------------------------------------------
    # DO NOT VERIFY TWICE
    # --------------------------------------------------------

    if queue_entry.get(
        "queue_access_verified",
        False,
    ) is True:

        raise HTTPException(
            status_code=400,
            detail=(
                "Patient has already been "
                "added to the doctor queue"
            ),
        )


    # --------------------------------------------------------
    # CONSUME QR TOKEN
    #
    # This prevents the same QR from being used twice.
    # --------------------------------------------------------

    consumed = qr_tokens_collection.update_one(
        {
            "_id":
                qr_record["_id"],

            "used_at":
                {
                    "$exists":
                        False
                },
        },

        {
            "$set":
                {
                    "used_at":
                        datetime.now(timezone.utc),

                    "used_by":
                        logged_in_patient,
                }
        },
    )


    if consumed.modified_count != 1:

        raise HTTPException(
            status_code=401,
            detail=(
                "Invalid, expired, or "
                "already used QR token"
            ),
        )


    # --------------------------------------------------------
    # MOVE PATIENT TO DOCTOR QUEUE
    #
    # BEFORE:
    #
    # WAITING_FOR_RECEPTION
    #
    # AFTER:
    #
    # WAITING
    # --------------------------------------------------------

    updated_at = datetime.now(
        timezone.utc
    )


    queue_update = queue_collection.update_one(
        {
            "_id":
                queue_entry["_id"],

            "status":
                QueueStatus.WAITING_FOR_RECEPTION.value,

            "queue_access_verified":
                {
                    "$ne":
                        True
                },
        },

        {
            "$set":
                {
                    "queue_access_verified":
                        True,

                    "queue_access_verified_at":
                        updated_at,

                    "status":
                        QueueStatus.WAITING.value,

                    "updated_at":
                        updated_at,
                }
        },
    )


    if queue_update.modified_count != 1:

        raise HTTPException(
            status_code=409,
            detail=(
                "Queue status changed before "
                "QR verification could be completed"
            ),
        )


    # ========================================================
    # NOW RECALCULATE DOCTOR QUEUE
    #
    # This calls your existing:
    #
    # recalculate_queue_state()
    #
    # which handles:
    #
    # 1. Queue position
    # 2. ML waiting-time prediction
    # 3. Probability values
    # 4. Bayesian expected wait
    # 5. Final risk level
    # ========================================================

    await recalculate_queue_state(
        queue_entry["department"]
    )


    # --------------------------------------------------------
    # GET UPDATED PATIENT
    # --------------------------------------------------------

    updated_patient = queue_collection.find_one(
        {
            "_id":
                queue_entry["_id"]
        }
    )

    if not updated_patient:

        raise HTTPException(
            status_code=500,
            detail="Queue state could not be refreshed after verification",
        )


    # --------------------------------------------------------
    # RETURN UPDATED STATE
    # --------------------------------------------------------

    return QRVerificationResponse(
        valid=True,

        patient_email=
            logged_in_patient,

        department=
            updated_patient["department"],

        token_number=
            updated_patient["token_number"],

        status=
            updated_patient["status"],
    )