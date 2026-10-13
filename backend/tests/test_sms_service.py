import unittest
from unittest.mock import patch, AsyncMock, MagicMock
import asyncio

from app.services.sms_service import normalize_phone_number, mask_phone_number, SMSService
from app.services.queue_notification_handler import maybe_send_sms_queue_notification
from app.config import get_settings


class TestSMSService(unittest.TestCase):

    def test_normalize_phone_number_indian(self):
        # 10 digits directly
        self.assertEqual(normalize_phone_number("9876543210"), "9876543210")
        # With +91
        self.assertEqual(normalize_phone_number("+91 98765 43210"), "9876543210")
        # With leading 0
        self.assertEqual(normalize_phone_number("09876543210"), "9876543210")
        # With hyphens
        self.assertEqual(normalize_phone_number("+91-98765-43210"), "9876543210")
        # Invalid phone
        self.assertIsNone(normalize_phone_number("12345"))
        self.assertIsNone(normalize_phone_number("abc"))
        self.assertIsNone(normalize_phone_number(None))

    def test_normalize_phone_number_e164(self):
        self.assertEqual(normalize_phone_number("+14155552671"), "+14155552671")
        self.assertEqual(normalize_phone_number("+44 20 7183 8750"), "+442071838750")

    def test_mask_phone_number(self):
        self.assertEqual(mask_phone_number("9876543210"), "******3210")
        self.assertEqual(mask_phone_number(None), "None")
        self.assertEqual(mask_phone_number("123"), "****")

    def test_disabled_sms_skips(self):
        service = SMSService()
        settings = get_settings()
        old_enabled = settings.sms_enabled
        try:
            settings.sms_enabled = False
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(service.send_sms("9876543210", "Test message"))
            self.assertFalse(result)
        finally:
            settings.sms_enabled = old_enabled

    def test_queue_notification_handler_opt_in_gate(self):
        settings = get_settings()
        old_enabled = settings.sms_enabled
        try:
            settings.sms_enabled = True

            # Mock collections
            mock_users = MagicMock()
            # User opted out
            mock_users.find_one.return_value = {
                "email": "patient@gmail.com",
                "phone_number": "9876543210",
                "sms_opt_in": False,
            }
            mock_queue = MagicMock()

            queue_entry = {
                "_id": "test_id",
                "patient_email": "patient@gmail.com",
                "status": "waiting",
                "position": 3,
                "token_number": 42,
            }

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            sent = loop.run_until_complete(
                maybe_send_sms_queue_notification(
                    queue_entry,
                    mock_users,
                    mock_queue,
                )
            )
            self.assertFalse(sent)
        finally:
            settings.sms_enabled = old_enabled

    def test_duplicate_notification_suppression(self):
        settings = get_settings()
        old_enabled = settings.sms_enabled
        try:
            settings.sms_enabled = True

            mock_users = MagicMock()
            mock_users.find_one.return_value = {
                "email": "patient@gmail.com",
                "phone_number": "9876543210",
                "sms_opt_in": True,
            }
            mock_queue = MagicMock()

            # Entry already notified for position 3 and waiting
            queue_entry = {
                "_id": "test_id",
                "patient_email": "patient@gmail.com",
                "status": "waiting",
                "position": 3,
                "predicted_wait_minutes": 10.0,
                "last_notified_status": "waiting",
                "last_notified_position": 3,
                "last_notified_wait_minutes": 10.0,
                "token_number": 42,
            }

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            sent = loop.run_until_complete(
                maybe_send_sms_queue_notification(
                    queue_entry,
                    mock_users,
                    mock_queue,
                )
            )
            self.assertFalse(sent)
        finally:
            settings.sms_enabled = old_enabled


if __name__ == "__main__":
    unittest.main()
