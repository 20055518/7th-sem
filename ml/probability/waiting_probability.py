import os
import numpy as np
import pandas as pd
import joblib

from scipy.stats import norm
from sklearn.model_selection import train_test_split


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

TARGET_COLUMN = "waiting_time_minutes"


# --------------------------------------------------
# Load dataset and model
# --------------------------------------------------

df = pd.read_csv(DATASET_PATH)

model = joblib.load(MODEL_PATH)


# --------------------------------------------------
# Prepare data
# --------------------------------------------------

X = df[FEATURE_COLUMNS]
y = df[TARGET_COLUMN]


X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42
)


# --------------------------------------------------
# Generate predictions
# --------------------------------------------------

y_pred = model.predict(X_test)


# --------------------------------------------------
# Calculate residuals
# --------------------------------------------------

residuals = y_test.to_numpy() - y_pred

residual_mean = np.mean(residuals)
residual_std = np.std(residuals, ddof=1)


print("===================================")
print("INDIVIDUAL PROBABILITY MODEL")
print("===================================")

print(f"Threshold: {THRESHOLD} minutes")
print(f"Residual mean: {residual_mean:.4f}")
print(f"Residual standard deviation: {residual_std:.4f}")


# --------------------------------------------------
# Probability function
# --------------------------------------------------

def probability_wait_over_threshold(predicted_wait, threshold=THRESHOLD):
    """
    Estimate P(W > threshold | X)
    using the empirical residual distribution
    approximated as normal.
    """

    probability = 1 - norm.cdf(
        threshold,
        loc=predicted_wait + residual_mean,
        scale=residual_std
    )

    return float(np.clip(probability, 0.0, 1.0))


# --------------------------------------------------
# Test with sample patients
# --------------------------------------------------

sample_predictions = y_pred[:10]

print("\nSample probability estimates")
print("-----------------------------")

for i, predicted_wait in enumerate(sample_predictions, start=1):

    probability = probability_wait_over_threshold(
        predicted_wait
    )

    print(
        f"Case {i}: "
        f"Predicted wait = {predicted_wait:.2f} min, "
        f"P(W > 45) = {probability:.4f} "
        f"({probability * 100:.2f}%)"
    )


# --------------------------------------------------
# Probability model validation
# --------------------------------------------------

probabilities = np.array([
    probability_wait_over_threshold(prediction)
    for prediction in y_pred
])

actual_events = (
    y_test.to_numpy() > THRESHOLD
).astype(int)


# Brier score
brier_score = np.mean(
    (probabilities - actual_events) ** 2
)


print("\nProbability validation")
print("----------------------")

print(f"Brier Score: {brier_score:.4f}")


print("\n===================================")
print("PROBABILITY MODEL COMPLETED")
print("===================================")