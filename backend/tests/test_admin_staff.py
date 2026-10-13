import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.auth import create_access_token

client = TestClient(app)


class TestAdminStaffCreation(unittest.TestCase):
    def setUp(self):
        self.admin_token = create_access_token('admin@hospital.org', 'admin')
        self.headers = {'Authorization': f'Bearer {self.admin_token}'}

    def test_unauthorized_user_cannot_create_staff(self):
        patient_token = create_access_token('patient@hospital.org', 'patient')
        res = client.post(
            '/api/admin/users',
            json={
                'email': 'unauthorized_doc@hospital.org',
                'password': 'Password123!',
                'role': 'doctor',
            },
            headers={'Authorization': f'Bearer {patient_token}'},
        )
        self.assertEqual(res.status_code, 403)

    def test_invalid_short_password_rejected(self):
        res = client.post(
            '/api/admin/users',
            json={
                'email': 'short_pass_doc@hospital.org',
                'password': 'short',
                'role': 'doctor',
            },
            headers=self.headers,
        )
        self.assertEqual(res.status_code, 422)
