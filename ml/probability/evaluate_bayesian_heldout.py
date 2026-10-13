import os
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    mean_absolute_error,
    mean_squared_error,
    r2_score
)


# ============================================================
# CONFIGURATION
# ============================================================

STATE_LABELS = [
    "Short",
    "Moderate",
    "Long",
    "Very Long"
]


# ============================================================
# PATH
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

DATASET_PATH = os.path.join(
    BASE_DIR,
    "datasets",
    "hospital_queue_dataset_5000.csv"
)


# ============================================================
# LOAD DATASET
# ============================================================

df = pd.read_csv(DATASET_PATH)

print("===================================")
print("FOUR-STATE BAYESIAN HELD-OUT EVALUATION")
print("===================================")

print(f"Total cases: {len(df)}")


# ============================================================
# TRAIN / TEST SPLIT
# ============================================================

train_df, test_df = train_test_split(
    df,
    test_size=0.20,
    random_state=42
)

train_df = train_df.copy()
test_df = test_df.copy()

print(f"Training cases: {len(train_df)}")
print(f"Testing cases : {len(test_df)}")


# ============================================================
# WAITING-TIME STATE
# ============================================================

def waiting_state(value):

    if value <= 15:
        return "Short"

    elif value <= 30:
        return "Moderate"

    elif value <= 60:
        return "Long"

    else:
        return "Very Long"


train_df["waiting_state"] = (
    train_df["waiting_time_minutes"]
    .apply(waiting_state)
)

test_df["waiting_state"] = (
    test_df["waiting_time_minutes"]
    .apply(waiting_state)
)


# ============================================================
# EVIDENCE STATE FUNCTIONS
# ============================================================

def congestion_state(value):

    if value <= 0.30:
        return "Low"

    elif value <= 0.60:
        return "Medium"

    else:
        return "High"


def patients_state(value):

    if value <= 5:
        return "Low"

    elif value <= 10:
        return "Medium"

    else:
        return "High"


def queue_state(value):

    if value <= 10:
        return "Low"

    elif value <= 20:
        return "Medium"

    else:
        return "High"


def doctor_status(value):

    if value == 1:
        return "Available"

    return "Unavailable"


def doctor_delay_state(value):

    if value <= 5:
        return "Low"

    elif value <= 15:
        return "Medium"

    else:
        return "High"


def historical_wait_state(value):

    if value <= 15:
        return "Short"

    elif value <= 30:
        return "Moderate"

    elif value <= 60:
        return "Long"

    else:
        return "Very Long"


def historical_queue_state(value):

    if value <= 10:
        return "Low"

    elif value <= 20:
        return "Medium"

    else:
        return "High"


def arrival_period(value):

    if value <= 11:
        return "Morning"

    elif value <= 15:
        return "Afternoon"

    elif value <= 19:
        return "Evening"

    else:
        return "Night"


# ============================================================
# CREATE EVIDENCE COLUMNS
# ============================================================

def prepare_evidence(data):

    data = data.copy()

    data["congestion_state"] = (
        data["queue_congestion"]
        .apply(congestion_state)
    )

    data["patients_ahead_state"] = (
        data["patients_ahead"]
        .apply(patients_state)
    )

    data["queue_length_state"] = (
        data["queue_length"]
        .apply(queue_state)
    )

    data["doctor_status"] = (
        data["doctor_available"]
        .apply(doctor_status)
    )

    data["doctor_delay_state"] = (
        data["doctor_delay_minutes"]
        .apply(doctor_delay_state)
    )

    data["historical_wait_state"] = (
        data["historical_average_wait"]
        .apply(historical_wait_state)
    )

    data["historical_queue_state"] = (
        data["historical_queue_length"]
        .apply(historical_queue_state)
    )

    data["arrival_period"] = (
        data["arrival_hour"]
        .apply(arrival_period)
    )

    return data


train_df = prepare_evidence(train_df)
test_df = prepare_evidence(test_df)


# ============================================================
# EVIDENCE FEATURES
# ============================================================

EVIDENCE_COLUMNS = [
    "congestion_state",
    "patients_ahead_state",
    "queue_length_state",
    "doctor_status",
    "doctor_delay_state",
    "historical_wait_state",
    "historical_queue_state",
    "arrival_period"
]


# ============================================================
# PRIOR PROBABILITIES
# ============================================================

total_train = len(train_df)

priors = {}

for state in STATE_LABELS:

    count = (
        train_df["waiting_state"]
        == state
    ).sum()

    priors[state] = (
        count / total_train
    )


print("\nTraining Prior Probabilities")
print("-----------------------------------")

for state in STATE_LABELS:

    print(
        f"{state:10} : "
        f"{priors[state]:.4f} "
        f"({priors[state] * 100:.2f}%)"
    )


# ============================================================
# PRECOMPUTE CONDITIONAL PROBABILITIES
# ============================================================

print("\nCalculating training likelihoods...")


likelihood_table = {}


for feature in EVIDENCE_COLUMNS:

    likelihood_table[feature] = {}

    feature_values = (
        train_df[feature]
        .unique()
    )

    for value in feature_values:

        likelihood_table[
            feature
        ][value] = {}

        for state in STATE_LABELS:

            state_rows = train_df[
                train_df["waiting_state"]
                == state
            ]

            state_count = len(
                state_rows
            )

            matching_count = (
                (
                    state_rows[feature]
                    == value
                )
                .sum()
            )

            number_of_values = (
                train_df[feature]
                .nunique()
            )

            # Laplace smoothing

            probability = (
                matching_count + 1
            ) / (
                state_count
                + number_of_values
            )

            likelihood_table[
                feature
            ][value][state] = probability


print("Likelihood calculation completed.")


# ============================================================
# BAYESIAN PREDICTION
# ============================================================

def predict_probabilities(row):

    scores = {}

    for state in STATE_LABELS:

        score = priors[state]

        for feature in EVIDENCE_COLUMNS:

            value = row[feature]

            likelihood = (
                likelihood_table
                .get(feature, {})
                .get(value, {})
                .get(state, 1e-6)
            )

            score *= likelihood

        scores[state] = score


    total_score = sum(
        scores.values()
    )


    if total_score == 0:

        return {
            state: priors[state]
            for state in STATE_LABELS
        }


    return {
        state:
        scores[state] / total_score
        for state in STATE_LABELS
    }


# ============================================================
# TEST SET PREDICTIONS
# ============================================================

print("\nGenerating Bayesian predictions...")


posterior_probabilities = []

predicted_states = []

expected_wait_times = []


STATE_MIDPOINTS = {
    "Short": 7.5,
    "Moderate": 23.0,
    "Long": 45.0,
    "Very Long": 75.0
}


for _, row in test_df.iterrows():

    posterior = predict_probabilities(
        row
    )

    posterior_probabilities.append(
        posterior
    )


    predicted_state = max(
        posterior,
        key=posterior.get
    )

    predicted_states.append(
        predicted_state
    )


    expected_wait = sum(
        posterior[state]
        * STATE_MIDPOINTS[state]
        for state in STATE_LABELS
    )

    expected_wait_times.append(
        expected_wait
    )


print("Prediction completed.")


# ============================================================
# ACTUAL VALUES
# ============================================================

actual_states = (
    test_df["waiting_state"]
    .to_numpy()
)

actual_waiting_times = (
    test_df["waiting_time_minutes"]
    .to_numpy()
)

expected_wait_times = np.array(
    expected_wait_times
)


# ============================================================
# CLASSIFICATION METRICS
# ============================================================

accuracy = accuracy_score(
    actual_states,
    predicted_states
)

precision = precision_score(
    actual_states,
    predicted_states,
    labels=STATE_LABELS,
    average="macro",
    zero_division=0
)

recall = recall_score(
    actual_states,
    predicted_states,
    labels=STATE_LABELS,
    average="macro",
    zero_division=0
)

f1 = f1_score(
    actual_states,
    predicted_states,
    labels=STATE_LABELS,
    average="macro",
    zero_division=0
)


# ============================================================
# CONFUSION MATRIX
# ============================================================

cm = confusion_matrix(
    actual_states,
    predicted_states,
    labels=STATE_LABELS
)


# ============================================================
# WAITING-TIME METRICS
# ============================================================

mae = mean_absolute_error(
    actual_waiting_times,
    expected_wait_times
)

rmse = np.sqrt(
    mean_squared_error(
        actual_waiting_times,
        expected_wait_times
    )
)

r2 = r2_score(
    actual_waiting_times,
    expected_wait_times
)


# ============================================================
# OUTPUT
# ============================================================

print("\n===================================")
print("FOUR-STATE BAYESIAN RESULTS")
print("===================================")

print(
    f"Accuracy        : {accuracy:.4f}"
)

print(
    f"Macro Precision : {precision:.4f}"
)

print(
    f"Macro Recall    : {recall:.4f}"
)

print(
    f"Macro F1        : {f1:.4f}"
)


print("\nConfusion Matrix")
print("-----------------------------------")

print(
    pd.DataFrame(
        cm,
        index=STATE_LABELS,
        columns=STATE_LABELS
    )
)


print("\nBayesian Expected Waiting-Time")
print("-----------------------------------")

print(
    f"MAE  : {mae:.2f} minutes"
)

print(
    f"RMSE : {rmse:.2f} minutes"
)

print(
    f"R²   : {r2:.4f}"
)


print("\n===================================")
print("FOUR-STATE BAYESIAN EVALUATION COMPLETED")
print("===================================")