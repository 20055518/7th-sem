import os
import numpy as np
import pandas as pd
import joblib

from scipy.stats import norm


# --------------------------------------------------
# Paths
# --------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATASET_PATH = os.path.join(
    BASE_DIR,
    "datasets",
    "consultations.csv"
)

MODEL_PATH = os.path.join(
    BASE_DIR,
    "models",
    "linear_regression.pkl"
)


# --------------------------------------------------
# Configuration
# --------------------------------------------------

THRESHOLD = 45
CONGESTION_THRESHOLD = 0.50


FEATURE_COLUMNS = [
    "patients_ahead",
    "queue_length",
    "average_consultation_minutes",
    "doctor_delay_minutes",
    "completed_patients",
    "doctor_available",
    "arrival_hour",
    "day_of_week",
    "no_show_probability",
    "queue_congestion",
    "historical_average_wait"
]


# --------------------------------------------------
# Load data and model
# --------------------------------------------------

df = pd.read_csv(DATASET_PATH)

model = joblib.load(MODEL_PATH)


# --------------------------------------------------
# Calculate residual distribution
# --------------------------------------------------

X = df[FEATURE_COLUMNS]
y = df["waiting_time_minutes"]

predictions = model.predict(X)

residuals = y.to_numpy() - predictions

residual_mean = np.mean(residuals)
residual_std = np.std(residuals, ddof=1)


# --------------------------------------------------
# Phase 7 probability
# --------------------------------------------------

def calculate_probability(predicted_wait):

    probability = 1 - norm.cdf(
        THRESHOLD,
        loc=predicted_wait + residual_mean,
        scale=residual_std
    )

    return float(
        np.clip(probability, 0.0, 1.0)
    )


# --------------------------------------------------
# Bayesian likelihoods
# --------------------------------------------------

df["H"] = (
    df["waiting_time_minutes"] > THRESHOLD
)

df["high_congestion"] = (
    df["queue_congestion"] > CONGESTION_THRESHOLD
)

df["doctor_unavailable"] = (
    df["doctor_available"] == 0
)

df["joint_evidence"] = (
    df["high_congestion"]
    &
    df["doctor_unavailable"]
)


H_cases = df["H"].sum()

not_H_cases = (~df["H"]).sum()

joint_H_cases = (
    df["H"]
    &
    df["joint_evidence"]
).sum()

joint_not_H_cases = (
    (~df["H"])
    &
    df["joint_evidence"]
).sum()


P_E_given_H = (
    joint_H_cases / H_cases
)

P_E_given_not_H = (
    joint_not_H_cases / not_H_cases
)


# --------------------------------------------------
# Bayesian update
# --------------------------------------------------

def bayesian_update(prior):

    prior = float(
        np.clip(prior, 0.0, 1.0)
    )

    prior_not = 1.0 - prior

    numerator = (
        P_E_given_H
        * prior
    )

    denominator = (
        (
            P_E_given_H
            * prior
        )
        +
        (
            P_E_given_not_H
            * prior_not
        )
    )

    if denominator == 0:

        return prior

    posterior = numerator / denominator

    return float(
        np.clip(posterior, 0.0, 1.0)
    )


# --------------------------------------------------
# Test individual cases
# --------------------------------------------------

print("===================================")
print("INDIVIDUAL BAYESIAN PREDICTION")
print("===================================")

print(
    f"Threshold: {THRESHOLD} minutes"
)

print(
    f"Residual std: "
    f"{residual_std:.4f}"
)

print(
    "\nEvidence:"
    "\nHigh congestion + "
    "Doctor unavailable"
)


print("\nSample predictions")
print("-------------------")


for i in range(10):

    predicted_wait = predictions[i]

    prior = calculate_probability(
        predicted_wait
    )

    posterior = bayesian_update(
        prior
    )

    print(
        f"\nCase {i + 1}"
    )

    print(
        f"Predicted wait : "
        f"{predicted_wait:.2f} min"
    )

    print(
        f"Prior P(W > 45): "
        f"{prior:.4f} "
        f"({prior * 100:.2f}%)"
    )

    print(
        f"Posterior       : "
        f"{posterior:.4f} "
        f"({posterior * 100:.2f}%)"
    )


print("\n===================================")
print("INDIVIDUAL BAYESIAN PREDICTION COMPLETED")
print("===================================")