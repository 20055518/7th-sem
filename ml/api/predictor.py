import os
import joblib
import pandas as pd


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
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
# FOUR-STATE BAYESIAN CONFIGURATION
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
# LOAD EXISTING LINEAR MODEL
# ============================================================

preprocessor = joblib.load(
    PREPROCESSOR_PATH
)

linear_model = joblib.load(
    LINEAR_MODEL_PATH
)


# ============================================================
# BAYESIAN STATE FUNCTIONS
# ============================================================

def congestion_state(value):

    if value <= 0.30:
        return "Low"

    elif value <= 0.60:
        return "Medium"

    return "High"


def patients_state(value):

    if value <= 5:
        return "Low"

    elif value <= 10:
        return "Medium"

    return "High"


def queue_state(value):

    if value <= 10:
        return "Low"

    elif value <= 20:
        return "Medium"

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

    return "High"


def historical_wait_state(value):

    if value <= 15:
        return "Short"

    elif value <= 30:
        return "Moderate"

    elif value <= 60:
        return "Long"

    return "Very Long"


def historical_queue_state(value):

    if value <= 10:
        return "Low"

    elif value <= 20:
        return "Medium"

    return "High"


def arrival_period(value):

    if value <= 11:
        return "Morning"

    elif value <= 15:
        return "Afternoon"

    elif value <= 19:
        return "Evening"

    return "Night"


# ============================================================
# PREPARE BAYESIAN EVIDENCE
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


# ============================================================
# TRAIN BAYESIAN MODEL FROM TRAINING DATA
# ============================================================
#
# The production predictor needs the Bayesian probability
# tables. They are learned from the training portion of the
# existing dataset only.
#
# The test set is NOT used here.
# ============================================================

def waiting_state(value):

    if value <= 15:
        return "Short"

    elif value <= 30:
        return "Moderate"

    elif value <= 60:
        return "Long"

    return "Very Long"


def build_bayesian_model():

    dataset_path = os.path.join(
        BASE_DIR,
        "datasets",
        "hospital_queue_dataset_5000.csv"
    )

    df = pd.read_csv(
        dataset_path
    )

    from sklearn.model_selection import train_test_split

    train_df, _ = train_test_split(
        df,
        test_size=0.20,
        random_state=42
    )

    train_df = train_df.copy()

    train_df["waiting_state"] = (
        train_df["waiting_time_minutes"]
        .apply(waiting_state)
    )

    train_df = prepare_evidence(
        train_df
    )

    total_train = len(
        train_df
    )

    # --------------------------------------------------------
    # PRIORS
    # --------------------------------------------------------

    priors = {}

    for state in STATE_LABELS:

        count = (
            train_df["waiting_state"]
            == state
        ).sum()

        priors[state] = (
            count / total_train
        )

    # --------------------------------------------------------
    # CONDITIONAL LIKELIHOODS
    # --------------------------------------------------------

    likelihood_table = {}

    for feature in EVIDENCE_COLUMNS:

        likelihood_table[feature] = {}

        feature_values = (
            train_df[feature]
            .unique()
        )

        number_of_values = (
            train_df[feature]
            .nunique()
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

    return (
        priors,
        likelihood_table
    )


# Build once when the module loads.
PRIORS, LIKELIHOOD_TABLE = (
    build_bayesian_model()
)


# ============================================================
# BAYESIAN PREDICTION
# ============================================================

def bayesian_predict(row):

    scores = {}

    for state in STATE_LABELS:

        score = PRIORS[state]

        for feature in EVIDENCE_COLUMNS:

            value = row[feature]

            likelihood = (
                LIKELIHOOD_TABLE
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
            state: PRIORS[state]
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
# RISK LEVEL
# ============================================================

def calculate_risk(probabilities):

    very_long_probability = (
        probabilities["Very Long"]
    )

    long_or_more_probability = (
        probabilities["Long"]
        + probabilities["Very Long"]
    )

    if very_long_probability >= 0.60:
        return "Very High"

    if long_or_more_probability >= 0.60:
        return "High"

    if long_or_more_probability >= 0.30:
        return "Moderate"

    return "Low"


# ============================================================
# MAIN PREDICTION FUNCTION
# ============================================================

def predict_queue(input_data):

    """
    Generate waiting-time and Bayesian queue prediction.

    input_data must contain the same feature columns used
    by the existing Linear Regression preprocessing pipeline.
    """

    data = pd.DataFrame(
        [input_data]
    )

    # --------------------------------------------------------
    # Linear Regression
    # --------------------------------------------------------

    linear_input = data.copy()

    X_processed = (
        preprocessor.transform(
            linear_input
        )
    )

    linear_prediction = (
        linear_model.predict(
            X_processed
        )[0]
    )

    # Prevent impossible negative wait.
    linear_prediction = max(
        float(linear_prediction),
        0.0
    )

    # --------------------------------------------------------
    # Bayesian
    # --------------------------------------------------------

    evidence_data = prepare_evidence(
        data
    )

    (
        probabilities,
        expected_wait,
        predicted_state
    ) = bayesian_predict(
        evidence_data.iloc[0]
    )

    risk_level = calculate_risk(
        probabilities
    )

        # --------------------------------------------------------
    # DERIVED WAITING PROBABILITIES
    # --------------------------------------------------------

    probability_short = (
        probabilities["Short"]
    )

    probability_moderate = (
        probabilities["Moderate"]
    )

    probability_long = (
        probabilities["Long"]
    )

    probability_very_long = (
        probabilities["Very Long"]
    )

    # Probability that the patient will
    # experience a Long OR Very Long wait.
    probability_long_or_more = (
        probability_long
        + probability_very_long
    )

    # --------------------------------------------------------
    # FINAL RESPONSE
    # --------------------------------------------------------

    return {

        # Primary numerical prediction
        "predicted_wait_minutes":
            round(
                linear_prediction,
                2
            ),

        # Most probable Bayesian state
        "bayesian_state":
            predicted_state,

        # Individual waiting-state probabilities
        "probability_short":
            round(
                probability_short,
                4
            ),

        "probability_moderate":
            round(
                probability_moderate,
                4
            ),

        "probability_long":
            round(
                probability_long,
                4
            ),

        "probability_very_long":
            round(
                probability_very_long,
                4
            ),

        # Important application-level probability
        "probability_long_or_more":
            round(
                probability_long_or_more,
                4
            ),

        # Keep the complete probability distribution
        "bayesian_probabilities": {

            "Short":
                round(
                    probability_short,
                    4
                ),

            "Moderate":
                round(
                    probability_moderate,
                    4
                ),

            "Long":
                round(
                    probability_long,
                    4
                ),

            "Very Long":
                round(
                    probability_very_long,
                    4
                )
        },

        # Bayesian expected waiting time
        "bayesian_expected_wait_minutes":
            round(
                float(expected_wait),
                2
            ),

        # Risk classification
        "risk_level":
            risk_level
    }