import unittest
from datetime import datetime, timedelta, timezone
from jose import jwt

from app.auth import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.config import get_settings

settings = get_settings()


class TestAuth(unittest.TestCase):
    def test_password_hashing_and_verification(self):
        password = "SecurePassword123!"
        hashed = hash_password(password)

        self.assertNotEqual(password, hashed)
        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password("WrongPassword", hashed))

    def test_create_access_token(self):
        subject = "testuser@hospital.org"
        role = "doctor"

        token = create_access_token(subject, role)
        self.assertIsInstance(token, str)
        self.assertTrue(len(token) > 20)

        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )

        self.assertEqual(payload["sub"], subject)
        self.assertEqual(payload["role"], role)
        self.assertIn("exp", payload)

    def test_expired_token_handling(self):
        subject = "expired@hospital.org"
        role = "patient"
        past_time = datetime.now(timezone.utc) - timedelta(minutes=10)

        expired_payload = {
            "sub": subject,
            "role": role,
            "exp": past_time,
        }

        expired_token = jwt.encode(
            expired_payload,
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )

        with self.assertRaises(jwt.ExpiredSignatureError):
            jwt.decode(
                expired_token,
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm],
            )


if __name__ == "__main__":
    unittest.main()
