from predictor import predict_queue


# ============================================================
# SAMPLE PATIENT / QUEUE INPUT
# ============================================================

sample_input = {
    "time_step": 10,
    "queue_congestion": 0.82,
    "patients_ahead": 15,
    "queue_length": 25,
    "doctor_available": 0,
    "doctor_delay_minutes": 12,
    "average_consultation_minutes": 18,
    "completed_patients": 8,
    "historical_average_wait": 40,
    "historical_queue_length": 18,
    "arrival_hour": 14,
    "no_show_probability": 0.15,
    "doctor_id": "D001",
    "department": "General",
    "patient_type": "Regular",
    "priority_level": "Normal",
    "appointment_type": "Walk-in",
    "day_of_week": "Monday"
}


# ============================================================
# RUN PREDICTION
# ============================================================

print("===================================")
print("ML PREDICTOR TEST")
print("===================================")

result = predict_queue(
    sample_input
)


# ============================================================
# DISPLAY RESULT
# ============================================================

print("\nPrediction Result")
print("-----------------------------------")

print(
    f"Predicted waiting time : "
    f"{result['predicted_wait_minutes']} minutes"
)

print(
    f"Bayesian state         : "
    f"{result['bayesian_state']}"
)

print(
    f"Bayesian expected wait : "
    f"{result['bayesian_expected_wait_minutes']} minutes"
)

print(
    f"Risk level             : "
    f"{result['risk_level']}"
)


# ============================================================
# WAITING-TIME PROBABILITIES
# ============================================================

print("\nWaiting-Time Probabilities")
print("-----------------------------------")

print(
    f"Short probability        : "
    f"{result['probability_short'] * 100:.2f}%"
)

print(
    f"Moderate probability     : "
    f"{result['probability_moderate'] * 100:.2f}%"
)

print(
    f"Long probability         : "
    f"{result['probability_long'] * 100:.2f}%"
)

print(
    f"Very Long probability    : "
    f"{result['probability_very_long'] * 100:.2f}%"
)

print(
    f"Long-or-more probability : "
    f"{result['probability_long_or_more'] * 100:.2f}%"
)


# ============================================================
# COMPLETE DISTRIBUTION
# ============================================================

print("\nBayesian Probability Distribution")
print("-----------------------------------")

for state, probability in (
    result["bayesian_probabilities"]
    .items()
):

    print(
        f"{state:12} : "
        f"{probability:.4f}"
    )


# ============================================================
# COMPLETED
# ============================================================

print("\n===================================")
print("ML PREDICTOR TEST COMPLETED")
print("===================================")