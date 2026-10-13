import os
import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import (
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

STATE_MIDPOINTS = {
    "Short": 7.5,
    "Moderate": 23.0,
    "Long": 45.0,
    "Very Long": 75.0
}


# ============================================================
# PATHS
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

PREPROCESSOR_PATH = os.path.join(
    BASE_DIR,
    "models",
    "preprocessor.pkl"
)

LINEAR_MODEL_PATH = os.path.join(
    BASE_DIR,
    "models",
    "linear_regression.pkl"
)

RESIDUAL_MODEL_PATH = os.path.join(
    BASE_DIR,
    "models",
    "residual_hybrid_model.pkl"
)


# ============================================================
# LOAD DATASET
# ============================================================

df = pd.read_csv(DATASET_PATH)

print("===================================")
print("RESIDUAL-BASED HYBRID MODEL")
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
# LOAD EXISTING PREPROCESSOR + LINEAR MODEL
# ============================================================

preprocessor = joblib.load(
    PREPROCESSOR_PATH
)

linear_model = joblib.load(
    LINEAR_MODEL_PATH
)


# ============================================================
# TARGET
# ============================================================

TARGET = "waiting_time_minutes"


# ============================================================
# PREPARE LINEAR REGRESSION FEATURES
# ============================================================

DROP_COLUMNS = [
    TARGET,
    "case_id",
    "queue_position"
]

X_train = train_df.drop(
    columns=DROP_COLUMNS
)

X_test = test_df.drop(
    columns=DROP_COLUMNS
)

y_train = train_df[TARGET].to_numpy()

y_test = test_df[TARGET].to_numpy()


# ============================================================
# PREPROCESS
# ============================================================

X_train_processed = preprocessor.transform(
    X_train
)

X_test_processed = preprocessor.transform(
    X_test
)


# ============================================================
# LINEAR REGRESSION PREDICTIONS
# ============================================================

linear_train_predictions = (
    linear_model.predict(
        X_train_processed
    )
)

linear_test_predictions = (
    linear_model.predict(
        X_test_processed
    )
)


# ============================================================
# FOUR-STATE BAYESIAN FUNCTIONS
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
# PREPARE BAYESIAN EVIDENCE
# ============================================================

def prepare_bayesian_data(data):

    data = data.copy()

    data["waiting_state"] = (
        data[TARGET]
        .apply(waiting_state)
    )

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


train_bayes = prepare_bayesian_data(
    train_df
)

test_bayes = prepare_bayesian_data(
    test_df
)


# ============================================================
# BAYESIAN EVIDENCE COLUMNS
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
# TRAINING-SET BAYESIAN PRIORS
# ============================================================

total_train = len(train_bayes)

priors = {}

for state in STATE_LABELS:

    count = (
        train_bayes["waiting_state"]
        == state
    ).sum()

    priors[state] = (
        count / total_train
    )


# ============================================================
# TRAINING-SET BAYESIAN LIKELIHOODS
# LAPLACE SMOOTHING
# ============================================================

likelihood_table = {}


for feature in EVIDENCE_COLUMNS:

    likelihood_table[feature] = {}

    feature_values = (
        train_bayes[feature]
        .unique()
    )

    number_of_values = (
        train_bayes[feature]
        .nunique()
    )

    for value in feature_values:

        likelihood_table[
            feature
        ][value] = {}

        for state in STATE_LABELS:

            state_rows = train_bayes[
                train_bayes["waiting_state"]
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

            probability = (
                matching_count + 1
            ) / (
                state_count
                + number_of_values
            )

            likelihood_table[
                feature
            ][value][state] = probability


# ============================================================
# BAYESIAN PREDICTION
# ============================================================

def bayesian_predict(row):

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

        probabilities = {
            state: priors[state]
            for state in STATE_LABELS
        }

    else:

        probabilities = {
            state:
            scores[state] / total_score
            for state in STATE_LABELS
        }


    expected_wait = sum(
        probabilities[state]
        * STATE_MIDPOINTS[state]
        for state in STATE_LABELS
    )


    return (
        probabilities,
        expected_wait
    )


# ============================================================
# GENERATE BAYESIAN FEATURES
# ============================================================

def generate_bayesian_features(data):

    probabilities_list = []
    expected_wait_list = []

    for _, row in data.iterrows():

        probabilities, expected_wait = (
            bayesian_predict(row)
        )

        probabilities_list.append(
            probabilities
        )

        expected_wait_list.append(
            expected_wait
        )


    features = pd.DataFrame({

        "bayesian_short": [
            p["Short"]
            for p in probabilities_list
        ],

        "bayesian_moderate": [
            p["Moderate"]
            for p in probabilities_list
        ],

        "bayesian_long": [
            p["Long"]
            for p in probabilities_list
        ],

        "bayesian_very_long": [
            p["Very Long"]
            for p in probabilities_list
        ],

        "bayesian_expected_wait":
            expected_wait_list
    })


    return features


# ============================================================
# GENERATE TRAINING BAYESIAN FEATURES
# ============================================================

train_bayesian_features = (
    generate_bayesian_features(
        train_bayes
    )
)


# ============================================================
# GENERATE TEST BAYESIAN FEATURES
# ============================================================

test_bayesian_features = (
    generate_bayesian_features(
        test_bayes
    )
)


# ============================================================
# STEP 1 — CALCULATE TRAINING RESIDUAL
# ============================================================

residual_train = (
    y_train
    - linear_train_predictions
)


print("\n===================================")
print("TRAINING RESIDUAL ANALYSIS")
print("===================================")

print(
    f"Mean residual : "
    f"{np.mean(residual_train):.4f}"
)

print(
    f"Std residual  : "
    f"{np.std(residual_train):.4f}"
)

print(
    f"Min residual  : "
    f"{np.min(residual_train):.4f}"
)

print(
    f"Max residual  : "
    f"{np.max(residual_train):.4f}"
)


# ============================================================
# STEP 2 — CREATE RESIDUAL MODEL FEATURES
# ============================================================

residual_train_features = pd.DataFrame({

    "linear_prediction":
        linear_train_predictions,

    "bayesian_short":
        train_bayesian_features[
            "bayesian_short"
        ].to_numpy(),

    "bayesian_moderate":
        train_bayesian_features[
            "bayesian_moderate"
        ].to_numpy(),

    "bayesian_long":
        train_bayesian_features[
            "bayesian_long"
        ].to_numpy(),

    "bayesian_very_long":
        train_bayesian_features[
            "bayesian_very_long"
        ].to_numpy(),

    "bayesian_expected_wait":
        train_bayesian_features[
            "bayesian_expected_wait"
        ].to_numpy()
})


residual_test_features = pd.DataFrame({

    "linear_prediction":
        linear_test_predictions,

    "bayesian_short":
        test_bayesian_features[
            "bayesian_short"
        ].to_numpy(),

    "bayesian_moderate":
        test_bayesian_features[
            "bayesian_moderate"
        ].to_numpy(),

    "bayesian_long":
        test_bayesian_features[
            "bayesian_long"
        ].to_numpy(),

    "bayesian_very_long":
        test_bayesian_features[
            "bayesian_very_long"
        ].to_numpy(),

    "bayesian_expected_wait":
        test_bayesian_features[
            "bayesian_expected_wait"
        ].to_numpy()
})


# ============================================================
# STEP 3 — TRAIN RESIDUAL CORRECTION MODEL
# ============================================================

residual_model = LinearRegression()

residual_model.fit(
    residual_train_features,
    residual_train
)


# ============================================================
# STEP 4 — PREDICT TEST RESIDUAL
# ============================================================

predicted_residual = (
    residual_model.predict(
        residual_test_features
    )
)


# ============================================================
# STEP 5 — FINAL HYBRID PREDICTION
# ============================================================

final_predictions = (
    linear_test_predictions
    + predicted_residual
)


# ============================================================
# PREVENT NEGATIVE WAITING TIMES
# ============================================================

final_predictions = np.maximum(
    final_predictions,
    0
)


# ============================================================
# LINEAR REGRESSION METRICS
# ============================================================

linear_mae = mean_absolute_error(
    y_test,
    linear_test_predictions
)

linear_rmse = np.sqrt(
    mean_squared_error(
        y_test,
        linear_test_predictions
    )
)

linear_r2 = r2_score(
    y_test,
    linear_test_predictions
)


# ============================================================
# BAYESIAN EXPECTED WAIT METRICS
# ============================================================

bayesian_expected_wait = (
    test_bayesian_features[
        "bayesian_expected_wait"
    ].to_numpy()
)

bayesian_mae = mean_absolute_error(
    y_test,
    bayesian_expected_wait
)

bayesian_rmse = np.sqrt(
    mean_squared_error(
        y_test,
        bayesian_expected_wait
    )
)

bayesian_r2 = r2_score(
    y_test,
    bayesian_expected_wait
)


# ============================================================
# RESIDUAL HYBRID METRICS
# ============================================================

hybrid_mae = mean_absolute_error(
    y_test,
    final_predictions
)

hybrid_rmse = np.sqrt(
    mean_squared_error(
        y_test,
        final_predictions
    )
)

hybrid_r2 = r2_score(
    y_test,
    final_predictions
)


# ============================================================
# IMPROVEMENT / CHANGE
# ============================================================

mae_improvement = (
    (
        linear_mae
        - hybrid_mae
    )
    / linear_mae
) * 100


rmse_improvement = (
    (
        linear_rmse
        - hybrid_rmse
    )
    / linear_rmse
) * 100


r2_change = (
    hybrid_r2
    - linear_r2
)


# ============================================================
# OUTPUT — LINEAR BASELINE
# ============================================================

print("\n===================================")
print("LINEAR REGRESSION BASELINE")
print("===================================")

print(
    f"MAE  : {linear_mae:.2f} minutes"
)

print(
    f"RMSE : {linear_rmse:.2f} minutes"
)

print(
    f"R²   : {linear_r2:.4f}"
)


# ============================================================
# OUTPUT — BAYESIAN
# ============================================================

print("\n===================================")
print("FOUR-STATE BAYESIAN COMPONENT")
print("===================================")

print(
    f"MAE  : {bayesian_mae:.2f} minutes"
)

print(
    f"RMSE : {bayesian_rmse:.2f} minutes"
)

print(
    f"R²   : {bayesian_r2:.4f}"
)

print(
    f"Mean Bayesian expected wait : "
    f"{np.mean(bayesian_expected_wait):.2f} minutes"
)


# ============================================================
# OUTPUT — RESIDUAL MODEL
# ============================================================

print("\n===================================")
print("RESIDUAL CORRECTION MODEL")
print("===================================")

print("Residual model target:")
print(
    "actual_waiting_time - linear_prediction"
)

print("\nResidual model features:")

for feature in residual_train_features.columns:

    print(
        f"  - {feature}"
    )


print("\nResidual model coefficients:")

for feature, coefficient in zip(
    residual_train_features.columns,
    residual_model.coef_
):

    print(
        f"  {feature}: "
        f"{coefficient:.6f}"
    )


print(
    f"\nResidual model intercept: "
    f"{residual_model.intercept_:.6f}"
)


# ============================================================
# OUTPUT — FINAL HYBRID
# ============================================================

print("\n===================================")
print("RESIDUAL HYBRID PERFORMANCE")
print("===================================")

print(
    f"MAE  : {hybrid_mae:.2f} minutes"
)

print(
    f"RMSE : {hybrid_rmse:.2f} minutes"
)

print(
    f"R²   : {hybrid_r2:.4f}"
)


# ============================================================
# OUTPUT — COMPARISON
# ============================================================

print("\n===================================")
print("COMPARISON WITH LINEAR REGRESSION")
print("===================================")

print(
    f"MAE improvement  : "
    f"{mae_improvement:.2f}%"
)

print(
    f"RMSE improvement : "
    f"{rmse_improvement:.2f}%"
)

print(
    f"R² change        : "
    f"{r2_change:.4f}"
)


# ============================================================
# SCIENTIFIC CONCLUSION
# ============================================================

print("\n===================================")
print("EXPERIMENT CONCLUSION")
print("===================================")

if (
    hybrid_mae < linear_mae
    and hybrid_rmse < linear_rmse
    and hybrid_r2 > linear_r2
):

    print(
        "Residual hybrid improved all three "
        "evaluation metrics on the held-out test set."
    )

elif (
    hybrid_mae < linear_mae
    or hybrid_rmse < linear_rmse
    or hybrid_r2 > linear_r2
):

    print(
        "Residual hybrid improved some metrics "
        "but not all metrics."
    )

else:

    print(
        "Residual hybrid did not improve "
        "Linear Regression on the held-out test set."
    )


# ============================================================
# SAVE RESIDUAL HYBRID MODEL
# ============================================================

residual_hybrid_package = {

    "model": residual_model,

    "features": list(
        residual_train_features.columns
    ),

    "state_labels": STATE_LABELS,

    "state_midpoints":
        STATE_MIDPOINTS,

    "linear_mae":
        linear_mae,

    "linear_rmse":
        linear_rmse,

    "linear_r2":
        linear_r2,

    "bayesian_mae":
        bayesian_mae,

    "bayesian_rmse":
        bayesian_rmse,

    "bayesian_r2":
        bayesian_r2,

    "hybrid_mae":
        hybrid_mae,

    "hybrid_rmse":
        hybrid_rmse,

    "hybrid_r2":
        hybrid_r2
}


joblib.dump(
    residual_hybrid_package,
    RESIDUAL_MODEL_PATH
)


print("\nResidual hybrid model saved to:")

print(
    RESIDUAL_MODEL_PATH
)


print("\n===================================")
print("RESIDUAL HYBRID COMPLETED")
print("===================================")