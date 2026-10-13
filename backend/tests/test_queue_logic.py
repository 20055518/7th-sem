import unittest

from app.queue_schemas import TriagePriority
from app.services.queue_service import (
    PRIORITY_ORDER,
    calculate_final_risk,
    get_priority_rank,
    normalize_risk_value,
)


class TestQueueLogic(unittest.IsolatedAsyncioTestCase):
    def test_priority_ranking_order(self):
        """Urgent patients must have lower rank index (served first) than normal."""
        urgent_rank = get_priority_rank({"priority": TriagePriority.URGENT.value})
        high_rank = get_priority_rank({"priority": TriagePriority.HIGH.value})
        medium_rank = get_priority_rank({"priority": TriagePriority.MEDIUM.value})
        normal_rank = get_priority_rank({"priority": TriagePriority.NORMAL.value})

        self.assertEqual(urgent_rank, 1)
        self.assertEqual(high_rank, 2)
        self.assertEqual(medium_rank, 3)
        self.assertEqual(normal_rank, 4)
        self.assertLess(urgent_rank, high_rank)
        self.assertLess(high_rank, medium_rank)
        self.assertLess(medium_rank, normal_rank)

    def test_normalize_risk_value(self):
        self.assertEqual(normalize_risk_value("URGENT"), "urgent")
        self.assertEqual(normalize_risk_value("Critical"), "urgent")
        self.assertEqual(normalize_risk_value("Emergency"), "urgent")
        self.assertEqual(normalize_risk_value("High"), "high")
        self.assertEqual(normalize_risk_value("Medium"), "medium")
        self.assertEqual(normalize_risk_value("Moderate"), "medium")
        self.assertEqual(normalize_risk_value("Low"), "low")
        self.assertEqual(normalize_risk_value(""), "")

    def test_calculate_final_risk_urgent_triage_override(self):
        """Nurse triage priority urgent should never be downgraded by low ML prediction."""
        prediction = {
            "risk_level": "low",
            "predicted_wait_minutes": 5.0,
            "probability_long_or_more": 0.05,
            "bayesian_expected_wait_minutes": 6.0,
        }

        risk = calculate_final_risk(
            prediction,
            priority=TriagePriority.URGENT.value,
            position=1,
            queue_length=2,
        )

        self.assertEqual(risk, "urgent")

    def test_calculate_final_risk_low(self):
        prediction = {
            "risk_level": "low",
            "predicted_wait_minutes": 8.0,
            "probability_long_or_more": 0.05,
            "bayesian_expected_wait_minutes": 7.5,
        }

        risk = calculate_final_risk(
            prediction,
            priority=TriagePriority.NORMAL.value,
            position=1,
            queue_length=2,
        )

        self.assertEqual(risk, "low")

    async def test_recalculate_queue_state_ml_fallback(self):
        from unittest.mock import patch
        from app.services.queue_service import recalculate_queue_state

        fake_entry = {
            "_id": "mock_id_123",
            "department": "Cardiology",
            "status": "waiting",
            "position": 2,
            "priority": "normal",
            "token_number": 10,
        }

        with patch("app.services.queue_service.queue_collection") as mock_coll, \
             patch("app.services.queue_service.build_ml_prediction", side_effect=Exception("Connection refused")):
            mock_coll.find.return_value = [fake_entry]

            # Should complete without raising 503 HTTPException
            await recalculate_queue_state("Cardiology")

            # Verify update_one was called with the fallback prediction fields
            self.assertTrue(mock_coll.update_one.called)
            update_call_args = mock_coll.update_one.call_args[0]
            update_data = update_call_args[1]["$set"]
            self.assertEqual(update_data["predicted_wait_minutes"], 0.0)
            self.assertEqual(update_data["bayesian_state"], "Short")
            self.assertEqual(update_data["risk_level"], "low")



    def test_nurse_assessment_temperature_and_pain_level(self):
        from app.queue_schemas import NurseAssessmentCreate
        from pydantic import ValidationError

        # Valid Celsius
        celsius = NurseAssessmentCreate(
            patient_email="patient@hospital.org",
            department="General",
            temperature=37.0,
        )
        self.assertEqual(celsius.temperature, 37.0)
        self.assertIsNone(celsius.pain_level)

        # Valid Fahrenheit
        fahrenheit = NurseAssessmentCreate(
            patient_email="patient@hospital.org",
            department="General",
            temperature=98.6,
        )
        self.assertEqual(fahrenheit.temperature, 98.6)

        # Out of bounds (<20 or >120)
        with self.assertRaises(ValidationError):
            NurseAssessmentCreate(
                patient_email="patient@hospital.org",
                department="General",
                temperature=15.0,
            )

        with self.assertRaises(ValidationError):
            NurseAssessmentCreate(
                patient_email="patient@hospital.org",
                department="General",
                temperature=130.0,
            )


if __name__ == "__main__":
    unittest.main()

