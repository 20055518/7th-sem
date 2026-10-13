from __future__ import annotations

import logging
import re
from typing import Any
import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Regex for matching 10-digit Indian numbers or E.164
_INDIAN_PHONE_REGEX = re.compile(r"^(?:\+91|91|0)?([6-9]\d{9})$")
_E164_REGEX = re.compile(r"^\+[1-9]\d{7,14}$")


def normalize_phone_number(raw_phone: str | None) -> str | None:
    """
    Normalizes input phone number:
    - Strips whitespace, hyphens, and brackets.
    - If valid 10-digit Indian mobile (starts with 6-9, with or without +91, 91, 0), returns 10-digit string.
    - If international E.164 (+<country_code><number>), returns clean E.164.
    - Returns None if invalid.
    """
    if not raw_phone:
        return None

    cleaned = re.sub(r"[\s\-\(\)\.]+", "", str(raw_phone).strip())
    if not cleaned:
        return None

    # Check for Indian mobile number pattern
    match_indian = _INDIAN_PHONE_REGEX.match(cleaned)
    if match_indian:
        return match_indian.group(1)  # 10-digit mobile number

    # Check for general E.164
    if _E164_REGEX.match(cleaned):
        return cleaned

    # Check if exactly 10 digits
    if re.match(r"^[6-9]\d{9}$", cleaned):
        return cleaned

    return None


def mask_phone_number(phone: str | None) -> str:
    """Masks phone number for safe logging: e.g. 'XXXXXX1234' or '+91XXXXX1234'."""
    if not phone:
        return "None"
    phone_str = str(phone).strip()
    if len(phone_str) <= 4:
        return "****"
    return f"{'*' * (len(phone_str) - 4)}{phone_str[-4:]}"


class SMSService:
    """
    Decoupled SMS Notification Service for CarePath.
    Supports Fast2SMS (Indian SMS Gateway) with fallback for generic HTTP POST gateways.
    Safe development mode: If SMS_ENABLED=false, skips sending and returns False safely.
    """

    def __init__(self) -> None:
        self.client_timeout = 6.0

    async def send_sms(self, phone_number: str, message: str) -> bool:
        """
        Sends an SMS to the designated phone number.
        Returns True on success, False on error or if SMS_ENABLED=false.
        Guarantees failure isolation (never raises exception).
        """
        if not settings.sms_enabled:
            logger.info("SMS notification skipped: SMS_ENABLED=false (Message: %s)", message)
            return False

        normalized = normalize_phone_number(phone_number)
        if not normalized:
            logger.warning("SMS dispatch skipped: Invalid phone number format (%s)", mask_phone_number(phone_number))
            return False

        if not settings.sms_api_key:
            logger.warning("SMS dispatch skipped: SMS_API_KEY is not configured (Message: %s)", message)
            return False

        masked = mask_phone_number(normalized)

        try:
            async with httpx.AsyncClient(timeout=self.client_timeout) as client:
                headers = {
                    "authorization": settings.sms_api_key,
                    "Content-Type": "application/json",
                }

                payload = {
                    "route": "q",
                    "message": message,
                    "language": "english",
                    "flash": 0,
                    "numbers": normalized,
                }

                response = await client.post(
                    settings.sms_api_url,
                    json=payload,
                    headers=headers,
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("return") is True:
                        logger.info("SMS sent successfully to %s", masked)
                        return True
                    else:
                        logger.warning("SMS gateway returned failure for %s: %s", masked, data.get("message", "Unknown"))
                        return False
                else:
                    logger.warning("SMS gateway HTTP %d for %s", response.status_code, masked)
                    return False

        except httpx.TimeoutException:
            logger.warning("SMS request timed out for %s (non-blocking)", masked)
            return False
        except Exception as exc:
            logger.error("Failed to send SMS to %s (non-blocking): %s", masked, str(exc))
            return False

    async def send_queue_notification(
        self,
        recipient_phone: str,
        token_number: int | str,
        position: int,
        estimated_wait_minutes: float | None = None,
        status: str = "waiting",
        department: str | None = None,
    ) -> bool:
        """
        Constructs concise, patient-facing operational SMS updates across all journey stages.
        Excludes all diagnosis, prescriptions, or sensitive medical history.
        """
        status_clean = str(status).lower().strip()
        dept_str = f" in {department}" if department else ""

        if status_clean == "called":
            message = (
                f"CarePath: Token #{token_number}, your turn has been called! "
                f"Please proceed immediately to your doctor{dept_str}."
            )
        elif status_clean == "skipped":
            message = (
                f"CarePath: Token #{token_number} was marked as absent. "
                "Please visit reception or speak with the hospital staff to requeue."
            )
        elif status_clean == "waiting_for_triage":
            message = (
                f"CarePath: Token #{token_number} registered{dept_str}. "
                "Please proceed to the Nurse Station for initial triage assessment."
            )
        elif status_clean == "waiting_for_reception":
            message = (
                f"CarePath: Token #{token_number}, your triage is complete! "
                "Please visit Reception to scan the QR code and join the doctor queue."
            )
        elif position <= 2 and position > 0:
            message = (
                f"CarePath Alert: Token #{token_number}, your turn is approaching! "
                f"Position: {position}. Please be near Doctor consultation room{dept_str}."
            )
        else:
            wait_text = f" (Est. wait: {int(estimated_wait_minutes)} mins)" if estimated_wait_minutes and estimated_wait_minutes > 0 else ""
            pos_text = f"Your queue position is {position}" if position > 0 else "You are in the queue"
            message = (
                f"CarePath: Token #{token_number}. {pos_text}{wait_text}{dept_str}. "
                "Thank you for your patience."
            )

        return await self.send_sms(recipient_phone, message)


sms_service = SMSService()
