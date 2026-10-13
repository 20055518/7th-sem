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
# Load dataset and model
# --------------------------------------------------

df = pd.read_csv(DATASET_PATH)

model = joblib.load(MODEL_PATH)


# --------------------------------------------------
# Linear Regression predictions
# --------------------------------------------------

X = df[FEATURE_COLUMNS]

predictions = model.predict(X)


# --------------------------------------------------
# Residual distribution
# --------------------------------------------------

y = df["waiting_time_minutes"].to_numpy()

residuals = y - predictions

residual_mean = np.mean(residuals)

residual_std = np.std(
    residuals,
    ddof=1
)


# --------------------------------------------------
# Phase 7 probability
# --------------------------------------------------

def calculate_prior(predicted_wait):

    probability = 1 - norm.cdf(
        THRESHOLD,
        loc=predicted_wait + residual_mean,
        scale=residual_std
    )

    return float(
        np.clip(probability, 0.0, 1.0)
    )


# --------------------------------------------------
# Define historical hypothesis/evidence
# --------------------------------------------------

df["H"] = (
    df["waiting_time_minutes"]
    > THRESHOLD
)

df["high_congestion"] = (
    df["queue_congestion"]
    > CONGESTION_THRESHOLD
)

df["doctor_unavailable"] = (
    df["doctor_available"] == 0
)


# --------------------------------------------------
# Calculate likelihoods
# --------------------------------------------------

def conditional_probability(evidence):

    H_count = df["H"].sum()

    not_H_count = (~df["H"]).sum()

    evidence_and_H = (
        evidence & df["H"]
    ).sum()

    evidence_and_not_H = (
        evidence & (~df["H"])
    ).sum()

    P_E_given_H = (
        evidence_and_H / H_count
    )

    P_E_given_not_H = (
        evidence_and_not_H / not_H_count
    )

    return (
        P_E_given_H,
        P_E_given_not_H
    )


# High congestion
P_HC_given_H, P_HC_given_not_H = (
    conditional_probability(
        df["high_congestion"]
    )
)


# Doctor unavailable
P_DU_given_H, P_DU_given_not_H = (
    conditional_probability(
        df["doctor_unavailable"]
    )
)


# Both conditions
joint_evidence = (
    df["high_congestion"]
    &
    df["doctor_unavailable"]
)

P_BOTH_given_H, P_BOTH_given_not_H = (
    conditional_probability(
        joint_evidence
    )
)


# --------------------------------------------------
# Bayesian update function
# --------------------------------------------------

def bayesian_update(
    prior,
    likelihood_H,
    likelihood_not_H
):

    prior = float(
        np.clip(prior, 0.0, 1.0)
    )

    prior_not = 1.0 - prior

    numerator = (
        likelihood_H
        * prior
    )

    denominator = (
        (
            likelihood_H
            * prior
        )
        +
        (
            likelihood_not_H
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
# Evidence-aware prediction
# --------------------------------------------------

def calculate_posterior(
    predicted_wait,
    high_congestion,
    doctor_unavailable
):

    prior = calculate_prior(
        predicted_wait
    )


    # No evidence
    if (
        not high_congestion
        and not doctor_unavailable
    ):

        return prior


    # Both conditions
    if (
        high_congestion
        and doctor_unavailable
    ):

        return bayesian_update(
            prior,
            P_BOTH_given_H,
            P_BOTH_given_not_H
        )


    # High congestion only
    if high_congestion:

        return bayesian_update(
            prior,
            P_HC_given_H,
            P_HC_given_not_H
        )


    # Doctor unavailable only
    if doctor_unavailable:

        return bayesian_update(
            prior,
            P_DU_given_H,
            P_DU_given_not_H
        )


# --------------------------------------------------
# Apply to dataset
# --------------------------------------------------

results = []

for i in range(len(df)):

    predicted_wait = predictions[i]

    high_congestion = bool(
        df.iloc[i]["high_congestion"]
    )

    doctor_unavailable = bool(
        df.iloc[i]["doctor_unavailable"]
    )

    prior = calculate_prior(
        predicted_wait
    )

    posterior = calculate_posterior(
        predicted_wait,
        high_congestion,
        doctor_unavailable
    )

    results.append({
        "predicted_wait": predicted_wait,
        "prior_probability": prior,
        "posterior_probability": posterior,
        "high_congestion": high_congestion,
        "doctor_unavailable": doctor_unavailable,
        "actual_wait": df.iloc[i][
            "waiting_time_minutes"
        ]
    })


results_df = pd.DataFrame(results)


# --------------------------------------------------
# Display sample results
# --------------------------------------------------

print("===================================")
print("EVIDENCE-AWARE BAYESIAN MODEL")
print("===================================")

print(
    f"Threshold: {THRESHOLD} minutes"
)

print(
    f"High congestion threshold: "
    f"> {CONGESTION_THRESHOLD}"
)

print(
    f"Residual std: "
    f"{residual_std:.4f}"
)


print("\nSample predictions")
print("-------------------")


for i in range(10):

    row = results_df.iloc[i]

    print(
        f"\nCase {i + 1}"
    )

    print(
        f"Predicted wait : "
        f"{row['predicted_wait']:.2f} min"
    )

    print(
        f"High congestion: "
        f"{row['high_congestion']}"
    )

    print(
        f"Doctor unavailable: "
        f"{row['doctor_unavailable']}"
    )

    print(
        f"Prior          : "
        f"{row['prior_probability']:.4f} "
        f"({row['prior_probability'] * 100:.2f}%)"
    )

    print(
        f"Posterior      : "
        f"{row['posterior_probability']:.4f} "
        f"({row['posterior_probability'] * 100:.2f}%)"
    )

    print(
        f"Actual wait    : "
        f"{row['actual_wait']:.2f} min"
    )


# --------------------------------------------------
# Summary
# --------------------------------------------------

print("\n===================================")
print("EVIDENCE-AWARE MODEL COMPLETED")
print("===================================")