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
# Predictions
# --------------------------------------------------

X = df[FEATURE_COLUMNS]

y_actual = df["waiting_time_minutes"].to_numpy()

predictions = model.predict(X)


# --------------------------------------------------
# Residual distribution
# --------------------------------------------------

residuals = y_actual - predictions

residual_mean = np.mean(residuals)

residual_std = np.std(
    residuals,
    ddof=1
)


# --------------------------------------------------
# Prior probability
# --------------------------------------------------

prior_probabilities = (
    1
    - norm.cdf(
        THRESHOLD,
        loc=predictions + residual_mean,
        scale=residual_std
    )
)

prior_probabilities = np.clip(
    prior_probabilities,
    0.0,
    1.0
)


# --------------------------------------------------
# Define Bayesian evidence
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
# Likelihood helper
# --------------------------------------------------

def calculate_likelihoods(evidence):

    H_count = df["H"].sum()

    not_H_count = (~df["H"]).sum()

    evidence_and_H = (
        evidence & df["H"]
    ).sum()

    evidence_and_not_H = (
        evidence & (~df["H"])
    ).sum()

    return (
        evidence_and_H / H_count,
        evidence_and_not_H / not_H_count
    )


# --------------------------------------------------
# Calculate likelihoods
# --------------------------------------------------

P_HC_H, P_HC_not_H = calculate_likelihoods(
    df["high_congestion"]
)

P_DU_H, P_DU_not_H = calculate_likelihoods(
    df["doctor_unavailable"]
)

joint_evidence = (
    df["high_congestion"]
    &
    df["doctor_unavailable"]
)

P_BOTH_H, P_BOTH_not_H = calculate_likelihoods(
    joint_evidence
)


# --------------------------------------------------
# Bayesian update
# --------------------------------------------------

def update_probability(
    prior,
    likelihood_H,
    likelihood_not_H
):

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

    return numerator / denominator


# --------------------------------------------------
# Calculate posterior probabilities
# --------------------------------------------------

posterior_probabilities = []


for i in range(len(df)):

    prior = prior_probabilities[i]

    high_congestion = bool(
        df.iloc[i]["high_congestion"]
    )

    doctor_unavailable = bool(
        df.iloc[i]["doctor_unavailable"]
    )


    # No evidence
    if (
        not high_congestion
        and not doctor_unavailable
    ):

        posterior = prior


    # Both evidence
    elif (
        high_congestion
        and doctor_unavailable
    ):

        posterior = update_probability(
            prior,
            P_BOTH_H,
            P_BOTH_not_H
        )


    # High congestion only
    elif high_congestion:

        posterior = update_probability(
            prior,
            P_HC_H,
            P_HC_not_H
        )


    # Doctor unavailable only
    else:

        posterior = update_probability(
            prior,
            P_DU_H,
            P_DU_not_H
        )


    posterior_probabilities.append(
        posterior
    )


posterior_probabilities = np.array(
    posterior_probabilities
)


# --------------------------------------------------
# Actual binary outcome
# --------------------------------------------------

actual_outcome = (
    y_actual > THRESHOLD
).astype(int)


# --------------------------------------------------
# Brier Scores
# --------------------------------------------------

prior_brier = np.mean(
    (
        prior_probabilities
        - actual_outcome
    ) ** 2
)

posterior_brier = np.mean(
    (
        posterior_probabilities
        - actual_outcome
    ) ** 2
)


# --------------------------------------------------
# Improvement
# --------------------------------------------------

brier_change = (
    prior_brier
    - posterior_brier
)

if prior_brier != 0:

    improvement_percentage = (
        brier_change
        / prior_brier
    ) * 100

else:

    improvement_percentage = 0


# --------------------------------------------------
# Output
# --------------------------------------------------

print("===================================")
print("BAYESIAN MODEL EVALUATION")
print("===================================")

print(
    f"Threshold: "
    f"{THRESHOLD} minutes"
)

print(
    f"Number of cases: "
    f"{len(df)}"
)

print("\nBrier Score")
print("-------------------")

print(
    f"Prior Brier Score     : "
    f"{prior_brier:.4f}"
)

print(
    f"Posterior Brier Score : "
    f"{posterior_brier:.4f}"
)

print(
    f"Brier Score change    : "
    f"{brier_change:.4f}"
)

print(
    f"Relative change       : "
    f"{improvement_percentage:.2f}%"
)


if posterior_brier < prior_brier:

    print(
        "\nResult: Posterior probability "
        "has a lower Brier Score."
    )

elif posterior_brier > prior_brier:

    print(
        "\nResult: Posterior probability "
        "has a higher Brier Score."
    )

else:

    print(
        "\nResult: Brier Scores are equal."
    )


print("\n===================================")
print("BAYESIAN EVALUATION COMPLETED")
print("===================================")