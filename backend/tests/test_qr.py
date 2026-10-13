import hashlib
import unittest

from app.qr import generate_qr_image_data, generate_qr_token


class TestQR(unittest.TestCase):
    def test_generate_qr_token(self):
        token1 = generate_qr_token()
        token2 = generate_qr_token()

        self.assertIsInstance(token1, str)
        self.assertIsInstance(token2, str)
        self.assertNotEqual(token1, token2)
        self.assertGreaterEqual(len(token1), 32)

    def test_generate_qr_image_data(self):
        token = generate_qr_token()
        image_data = generate_qr_image_data(token)

        self.assertTrue(image_data.startswith("data:image/png;base64,"))
        self.assertGreater(len(image_data), 100)

    def test_token_hash_consistency(self):
        token = "test_opaque_token_value_12345"
        hash1 = hashlib.sha256(token.encode("utf-8")).hexdigest()
        hash2 = hashlib.sha256(token.encode("utf-8")).hexdigest()

        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 64)


if __name__ == "__main__":
    unittest.main()
