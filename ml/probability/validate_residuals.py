import os
import numpy as np
import pandas as pd
import joblib

from scipy.stats import skew, kurtosis, normaltest
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
# Load dataset and model
# --------------------------------------------------

df = pd.read_csv(DATASET_PATH)

model = joblib.load(MODEL_PATH)


# --------------------------------------------------
# Features and target
# --------------------------------------------------

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


X = df[FEATURE_COLUMNS]
y = df[TARGET_COLUMN]


# --------------------------------------------------
# Same split used during training
# --------------------------------------------------

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42
)


# --------------------------------------------------
# Predictions and residuals
# --------------------------------------------------

y_pred = model.predict(X_test)

residuals = y_test.to_numpy() - y_pred


# --------------------------------------------------
# Statistics
# --------------------------------------------------

mean_residual = np.mean(residuals)
std_residual = np.std(residuals, ddof=1)

residual_skewness = skew(residuals)
residual_kurtosis = kurtosis(
    residuals,
    fisher=True
)

statistic, p_value = normaltest(residuals)


# --------------------------------------------------
# Quantiles
# --------------------------------------------------

quantiles = np.percentile(
    residuals,
    [1, 5, 25, 50, 75, 95, 99]
)


# --------------------------------------------------
# Output
# --------------------------------------------------

print("===================================")
print("RESIDUAL VALIDATION")
print("===================================")

print(f"Number of residuals: {len(residuals)}")

print("\nResidual statistics")
print("-------------------")

print(f"Mean       : {mean_residual:.4f}")
print(f"Std Dev    : {std_residual:.4f}")
print(f"Skewness   : {residual_skewness:.4f}")
print(f"Kurtosis   : {residual_kurtosis:.4f}")

print("\nResidual quantiles")
print("------------------")

print(f"1%   : {quantiles[0]:.4f}")
print(f"5%   : {quantiles[1]:.4f}")
print(f"25%  : {quantiles[2]:.4f}")
print(f"50%  : {quantiles[3]:.4f}")
print(f"75%  : {quantiles[4]:.4f}")
print(f"95%  : {quantiles[5]:.4f}")
print(f"99%  : {quantiles[6]:.4f}")

print("\nNormality test")
print("--------------")

print(f"Statistic : {statistic:.4f}")
print(f"P-value   : {p_value:.8f}")

print("\n===================================")
print("VALIDATION COMPLETED")
print("===================================")