from __future__ import annotations

import logging
import os
from typing import Any
from datetime import datetime, timezone

import firebase_admin
from firebase_admin import credentials, messaging

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_firebase_initialized = False


def initialize_firebase_admin() -> bool:
    """
    Safely initializes the Firebase Admin SDK if not already initialized.
    Checks:
    1. Existing default app in firebase_admin._apps
    2. Explicit FIREBASE_SERVICE_ACCOUNT_PATH or GOOGLE_APPLICATION_CREDENTIALS
    3. Default credentials fallback

    Never throws an unhandled exception or interrupts host execution.
    """
    global _firebase_initialized

    if _firebase_initialized:
        return True

    try:
        if firebase_admin._apps:
            _firebase_initialized = True
            logger.info("Firebase Admin already initialized.")
            return True

        sa_path = (
            os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
            or getattr(settings, "firebase_service_account_path", "")
            or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        )

        if sa_path and os.path.exists(sa_path):
            cred = credentials.Certificate(sa_path)
            firebase_admin.initialize_app(cred, {
                "projectId": settings.firebase_project_id
            })
            _firebase_initialized = True
            logger.info("Firebase Admin initialized using service account file: %s", sa_path)
            return True

        # Attempt default application credentials
        try:
            default_cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(default_cred, {
                "projectId": settings.firebase_project_id
            })
            _firebase_initialized = True
            logger.info("Firebase Admin initialized using Application Default Credentials.")
            return True
        except Exception:
            # If no service account is provided yet, do not fail backend startup
            logger.warning(
                "Firebase Admin credentials not found. FCM push notifications will be queued or skipped gracefully until service account is configured."
            )
            return False

    except Exception as exc:
        logger.error("Failed to initialize Firebase Admin SDK: %s", exc)
        return False


class FCMService:
    """
    Service responsible for dispatching Web Push Notifications via Firebase Cloud Messaging.
    All dispatch methods are non-blocking and fail safely without breaking queue workflows.
    """

    @staticmethod
    def is_available() -> bool:
        return initialize_firebase_admin()

    async def send_notification_to_token(
        self,
        token: str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> bool:
        """
        Sends an FCM message to a single web client device token.
        """
        if not token or not str(token).strip():
            return False

        if not self.is_available():
            logger.warning("FCM service unavailable: skipping push dispatch to token.")
            return False

        try:
            clean_token = str(token).strip()
            # Ensure all data dictionary values are stringified
            str_data = {str(k): str(v) for k, v in (data or {}).items()}

            message = messaging.Message(
                token=clean_token,
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=str_data,
                webpush=messaging.WebpushConfig(
                    notification=messaging.WebpushNotification(
                        title=title,
                        body=body,
                        icon="/logo.png",
                        badge="/logo.png",
                        tag="careplus-queue-alert",
                        renotify=True,
                    ),
                    fcm_options=messaging.WebpushFCMOptions(
                        link="/patient-dashboard"
                    ),
                ),
            )

            response = messaging.send(message)
            logger.info("Successfully sent FCM message: %s", response)
            return True

        except messaging.UnregisteredError:
            logger.warning("FCM token is unregistered/expired: %s", token[:15] + "...")
            return False
        except Exception as exc:
            logger.error("Error sending FCM notification: %s", exc)
            return False

    async def send_queue_notification(
        self,
        token: str,
        token_number: int | str,
        position: int,
        estimated_wait_minutes: float | None = None,
        status: str = "waiting",
        department: str | None = None,
    ) -> bool:
        """
        Formats patient-friendly queue status push notifications.
        Excludes sensitive clinical/diagnostic data.
        """
        status_clean = str(status).lower().strip()
        dept_str = f" in {department}" if department else ""

        if status_clean == "called":
            title = "Care+ Alert: Your Turn is Called!"
            body = (
                f"Token #{token_number}, your turn has been called! "
                f"Please proceed immediately to your doctor consultation{dept_str}."
            )
        elif status_clean == "skipped":
            title = "Care+ Queue Alert"
            body = (
                f"Token #{token_number} was marked as absent. "
                "Please speak with hospital reception to requeue."
            )
        elif status_clean == "waiting_for_triage":
            title = "Care+ Queue Confirmed"
            body = (
                f"Token #{token_number} registered{dept_str}. "
                "Please proceed to the Nurse Station for triage."
            )
        elif status_clean == "waiting_for_reception":
            title = "Care+ Triage Complete"
            body = (
                f"Token #{token_number}, triage complete! "
                "Please scan the QR code at Reception to enter the Doctor queue."
            )
        elif position <= 2 and position > 0:
            title = "Care+ Alert: Turn Approaching!"
            body = (
                f"Token #{token_number}, you are #{position} in line{dept_str}! "
                "Please be ready near the doctor consultation room."
            )
        else:
            title = "Care+ Queue Update"
            wait_text = f" (~{int(estimated_wait_minutes)} mins)" if estimated_wait_minutes and estimated_wait_minutes > 0 else ""
            pos_text = f"Position #{position}" if position > 0 else "In Queue"
            body = f"Token #{token_number}: {pos_text}{wait_text}{dept_str}. Thank you for waiting."

        data_payload = {
            "token_number": str(token_number),
            "position": str(position),
            "status": str(status),
            "department": str(department or ""),
            "click_action": "/patient-dashboard",
        }

        return await self.send_notification_to_token(
            token=token,
            title=title,
            body=body,
            data=data_payload,
        )


fcm_service = FCMService()


async def maybe_send_patient_fcm_notification(
    queue_entry: dict[str, Any],
    users_collection: Any,
    force_status: str | None = None,
    force_position: int | None = None,
) -> bool:
    """
    Non-blocking helper that checks if patient has enabled FCM notifications,
    looks up their token from MongoDB users_collection, and triggers FCM push notification.
    """
    try:
        patient_email = queue_entry.get("patient_email")
        if not patient_email:
            return False

        user = users_collection.find_one(
            {"email": patient_email.strip().lower()},
            {"fcm_token": 1, "notifications_enabled": 1},
        )
        if not user:
            return False

        if not user.get("notifications_enabled", False):
            return False

        fcm_token = user.get("fcm_token")
        if not fcm_token:
            return False

        status = force_status or queue_entry.get("status", "waiting")
        position = (
            force_position
            if force_position is not None
            else queue_entry.get("position", 0)
        )
        token_number = queue_entry.get("token_number", "")
        department = queue_entry.get("department", "")
        est_wait = queue_entry.get("estimated_wait_time_minutes")

        return await fcm_service.send_queue_notification(
            token=fcm_token,
            token_number=token_number,
            position=position,
            estimated_wait_minutes=est_wait,
            status=status,
            department=department,
        )
    except Exception as exc:
        logger.error("Failed in maybe_send_patient_fcm_notification: %s", exc)
        return False
