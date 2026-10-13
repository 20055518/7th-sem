import os
import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error


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


# ============================================================
# LOAD DATA
# ============================================================

df = pd.read_csv(DATASET_PATH)

print("===================================")
print("LINEAR REGRESSION RESIDUAL ANALYSIS")
print("===================================")

print(f"Total cases: {len(df)}")


# ============================================================
# SAME TRAIN / TEST SPLIT
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
# LOAD EXISTING MODEL
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
# PREPARE FEATURES
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
# LINEAR PREDICTIONS
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
# RESIDUALS
# ============================================================

train_residual = (
    y_train
    - linear_train_predictions
)

test_residual = (
    y_test
    - linear_test_predictions
)


# ============================================================
# BAYESIAN STATE FUNCTIONS
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
# PREPARE BAYESIAN DATA
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
# BAYESIAN EVIDENCE
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
# TRAINING PRIORS
# ============================================================

total_train = len(train_bayes)

priors = {}

for state in STATE_LABELS:

    count = (
        train_bayes["waiting_state"]
        == state
    ).sum()

    priors[state] = count / total_train


# ============================================================
# BAYESIAN LIKELIHOODS
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
                state_rows[feature]
                == value
            ).sum()

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

    predicted_state = max(
        probabilities,
        key=probabilities.get
    )

    return (
        probabilities,
        expected_wait,
        predicted_state
    )


# ============================================================
# GENERATE BAYESIAN OUTPUTS
# ============================================================

def generate_bayesian_outputs(data):

    probabilities_list = []
    expected_wait_list = []
    predicted_states = []

    for _, row in data.iterrows():

        (
            probabilities,
            expected_wait,
            predicted_state
        ) = bayesian_predict(row)

        probabilities_list.append(
            probabilities
        )

        expected_wait_list.append(
            expected_wait
        )

        predicted_states.append(
            predicted_state
        )

    return (
        probabilities_list,
        np.array(expected_wait_list),
        predicted_states
    )


(
    train_probabilities,
    train_expected_wait,
    train_predicted_states
) = generate_bayesian_outputs(
    train_bayes
)


(
    test_probabilities,
    test_expected_wait,
    test_predicted_states
) = generate_bayesian_outputs(
    test_bayes
)


# ============================================================
# CONVERT BAYESIAN PROBABILITIES
# ============================================================

train_probability_df = pd.DataFrame({

    "P_Short": [
        p["Short"]
        for p in train_probabilities
    ],

    "P_Moderate": [
        p["Moderate"]
        for p in train_probabilities
    ],

    "P_Long": [
        p["Long"]
        for p in train_probabilities
    ],

    "P_Very_Long": [
        p["Very Long"]
        for p in train_probabilities
    ]
})


test_probability_df = pd.DataFrame({

    "P_Short": [
        p["Short"]
        for p in test_probabilities
    ],

    "P_Moderate": [
        p["Moderate"]
        for p in test_probabilities
    ],

    "P_Long": [
        p["Long"]
        for p in test_probabilities
    ],

    "P_Very_Long": [
        p["Very Long"]
        for p in test_probabilities
    ]
})


# ============================================================
# RESIDUAL SUMMARY
# ============================================================

print("\n===================================")
print("RESIDUAL SUMMARY")
print("===================================")

print(
    f"Mean residual : "
    f"{np.mean(train_residual):.4f}"
)

print(
    f"Std residual  : "
    f"{np.std(train_residual):.4f}"
)

print(
    f"Mean absolute residual : "
    f"{np.mean(np.abs(train_residual)):.4f}"
)

print(
    f"Minimum residual : "
    f"{np.min(train_residual):.4f}"
)

print(
    f"Maximum residual : "
    f"{np.max(train_residual):.4f}"
)


# ============================================================
# RESIDUAL CORRELATION WITH BAYESIAN FEATURES
# ============================================================

analysis_df = pd.DataFrame({

    "residual":
        train_residual,

    "linear_prediction":
        linear_train_predictions,

    "bayesian_expected_wait":
        train_expected_wait,

    "P_Short":
        train_probability_df["P_Short"],

    "P_Moderate":
        train_probability_df["P_Moderate"],

    "P_Long":
        train_probability_df["P_Long"],

    "P_Very_Long":
        train_probability_df["P_Very_Long"]
})


print("\n===================================")
print("RESIDUAL CORRELATION ANALYSIS")
print("===================================")

correlations = (
    analysis_df
    .corr(numeric_only=True)
    ["residual"]
    .drop("residual")
    .sort_values(
        key=np.abs,
        ascending=False
    )
)


for feature, correlation in correlations.items():

    print(
        f"{feature:25s}: "
        f"{correlation:.4f}"
    )


# ============================================================
# RESIDUAL ANALYSIS BY BAYESIAN STATE
# ============================================================

state_analysis = pd.DataFrame({

    "actual_wait":
        y_train,

    "linear_prediction":
        linear_train_predictions,

    "residual":
        train_residual,

    "bayesian_state":
        train_predicted_states
})


print("\n===================================")
print("RESIDUAL ANALYSIS BY BAYESIAN STATE")
print("===================================")


for state in STATE_LABELS:

    state_rows = state_analysis[
        state_analysis["bayesian_state"]
        == state
    ]

    if len(state_rows) == 0:
        continue

    state_residuals = (
        state_rows["residual"]
        .to_numpy()
    )

    state_mae = np.mean(
        np.abs(state_residuals)
    )

    state_rmse = np.sqrt(
        np.mean(
            state_residuals ** 2
        )
    )

    state_mean = np.mean(
        state_residuals
    )

    print(
        f"\n{state}"
    )

    print(
        f"  Cases          : "
        f"{len(state_rows)}"
    )

    print(
        f"  Mean residual  : "
        f"{state_mean:.4f}"
    )

    print(
        f"  MAE            : "
        f"{state_mae:.4f}"
    )

    print(
        f"  RMSE           : "
        f"{state_rmse:.4f}"
    )


# ============================================================
# BAYESIAN EXPECTED WAIT — RESIDUAL BINS
# ============================================================

analysis_df["expected_wait_bin"] = pd.cut(
    analysis_df["bayesian_expected_wait"],
    bins=[
        -np.inf,
        15,
        30,
        45,
        60,
        np.inf
    ],
    labels=[
        "0-15",
        "16-30",
        "31-45",
        "46-60",
        "60+"
    ]
)


print("\n===================================")
print("RESIDUAL BY BAYESIAN EXPECTED WAIT")
print("===================================")


grouped = (
    analysis_df
    .groupby(
        "expected_wait_bin",
        observed=False
    )
    ["residual"]
    .agg(
        ["count", "mean"]
    )
)


for index, row in grouped.iterrows():

    print(
        f"{str(index):>6s} min"
        f" | Cases: {int(row['count']):4d}"
        f" | Mean residual: "
        f"{row['mean']:8.4f}"
    )


# ============================================================
# TEST SET PERFORMANCE CHECK
# ============================================================

test_mae = mean_absolute_error(
    y_test,
    linear_test_predictions
)

test_rmse = np.sqrt(
    mean_squared_error(
        y_test,
        linear_test_predictions
    )
)


print("\n===================================")
print("HELD-OUT LINEAR REGRESSION CHECK")
print("===================================")

print(
    f"Test MAE  : "
    f"{test_mae:.2f} minutes"
)

print(
    f"Test RMSE : "
    f"{test_rmse:.2f} minutes"
)


# ============================================================
# AUTOMATIC INTERPRETATION
# ============================================================

strongest_feature = correlations.index[0]
strongest_correlation = correlations.iloc[0]

print("\n===================================")
print("ANALYSIS INTERPRETATION")
print("===================================")

print(
    f"Strongest residual relationship: "
    f"{strongest_feature}"
)

print(
    f"Correlation: "
    f"{strongest_correlation:.4f}"
)

if abs(strongest_correlation) < 0.10:

    print(
        "\nFinding:"
    )

    print(
        "Bayesian features show very weak "
        "linear relationship with Linear "
        "Regression residuals."
    )

elif abs(strongest_correlation) < 0.30:

    print(
        "\nFinding:"
    )

    print(
        "Bayesian features show a weak "
        "relationship with Linear "
        "Regression residuals."
    )

else:

    print(
        "\nFinding:"
    )

    print(
        "At least one Bayesian feature shows "
        "a meaningful residual relationship."
    )


print("\n===================================")
print("RESIDUAL ANALYSIS COMPLETED")
print("===================================")