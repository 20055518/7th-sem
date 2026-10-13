import os
import pandas as pd


class BayesianWaitingTimeUpdater:

    # ============================================================
    # INITIALIZATION
    # ============================================================

    def __init__(self, dataset):

        self.df = dataset.copy()

        self._prepare_data()
        self._calculate_priors()


    # ============================================================
    # PREPARE DATA
    # ============================================================

    def _prepare_data(self):

        # --------------------------------------------------------
        # Waiting-time states
        # --------------------------------------------------------

        self.df["waiting_state"] = pd.cut(
            self.df["waiting_time_minutes"],
            bins=[
                -float("inf"),
                15,
                30,
                60,
                float("inf")
            ],
            labels=[
                "Short",
                "Moderate",
                "Long",
                "Very Long"
            ]
        )


        # --------------------------------------------------------
        # Queue congestion state
        # --------------------------------------------------------

        self.df["congestion_state"] = pd.cut(
            self.df["queue_congestion"],
            bins=[
                -float("inf"),
                0.30,
                0.60,
                float("inf")
            ],
            labels=[
                "Low",
                "Medium",
                "High"
            ]
        )


        # --------------------------------------------------------
        # Patients-ahead state
        # --------------------------------------------------------

        self.df["patients_ahead_state"] = pd.cut(
            self.df["patients_ahead"],
            bins=[
                -float("inf"),
                5,
                10,
                float("inf")
            ],
            labels=[
                "Low",
                "Medium",
                "High"
            ]
        )


        # --------------------------------------------------------
        # Queue-length state
        # --------------------------------------------------------

        self.df["queue_length_state"] = pd.cut(
            self.df["queue_length"],
            bins=[
                -float("inf"),
                10,
                20,
                float("inf")
            ],
            labels=[
                "Low",
                "Medium",
                "High"
            ]
        )


        # --------------------------------------------------------
        # Doctor availability
        # --------------------------------------------------------

        self.df["doctor_status"] = self.df[
            "doctor_available"
        ].map({
            1: "Available",
            0: "Unavailable"
        })


        # --------------------------------------------------------
        # Doctor delay state
        # --------------------------------------------------------

        self.df["doctor_delay_state"] = pd.cut(
            self.df["doctor_delay_minutes"],
            bins=[
                -float("inf"),
                5,
                15,
                float("inf")
            ],
            labels=[
                "Low",
                "Medium",
                "High"
            ]
        )


        # --------------------------------------------------------
        # Historical average wait state
        # --------------------------------------------------------

        self.df["historical_wait_state"] = pd.cut(
            self.df["historical_average_wait"],
            bins=[
                -float("inf"),
                15,
                30,
                60,
                float("inf")
            ],
            labels=[
                "Short",
                "Moderate",
                "Long",
                "Very Long"
            ]
        )


        # --------------------------------------------------------
        # Historical queue length state
        # --------------------------------------------------------

        self.df["historical_queue_state"] = pd.cut(
            self.df["historical_queue_length"],
            bins=[
                -float("inf"),
                10,
                20,
                float("inf")
            ],
            labels=[
                "Low",
                "Medium",
                "High"
            ]
        )


        # --------------------------------------------------------
        # Arrival hour state
        # --------------------------------------------------------

        self.df["arrival_period"] = pd.cut(
            self.df["arrival_hour"],
            bins=[
                -float("inf"),
                11,
                15,
                19,
                float("inf")
            ],
            labels=[
                "Morning",
                "Afternoon",
                "Evening",
                "Night"
            ]
        )


    # ============================================================
    # CALCULATE PRIOR PROBABILITIES
    # ============================================================

    def _calculate_priors(self):

        state_counts = (
            self.df["waiting_state"]
            .value_counts()
        )

        total = len(self.df)

        self.priors = {}

        for state in [
            "Short",
            "Moderate",
            "Long",
            "Very Long"
        ]:

            self.priors[state] = (
                state_counts.get(
                    state,
                    0
                )
                / total
            )


    # ============================================================
    # BAYESIAN PREDICTION
    # ============================================================

    def predict(
        self,
        queue_congestion,
        patients_ahead,
        queue_length,
        doctor_available,
        doctor_delay_minutes,
        historical_average_wait,
        historical_queue_length,
        arrival_hour
    ):

        # --------------------------------------------------------
        # Convert patient values into evidence states
        # --------------------------------------------------------

        congestion_state = self._categorize(
            queue_congestion,
            [0.30, 0.60],
            ["Low", "Medium", "High"]
        )

        patients_state = self._categorize(
            patients_ahead,
            [5, 10],
            ["Low", "Medium", "High"]
        )

        queue_state = self._categorize(
            queue_length,
            [10, 20],
            ["Low", "Medium", "High"]
        )

        doctor_status = (
            "Available"
            if doctor_available == 1
            else "Unavailable"
        )

        doctor_delay_state = self._categorize(
            doctor_delay_minutes,
            [5, 15],
            ["Low", "Medium", "High"]
        )

        historical_wait_state = self._categorize(
            historical_average_wait,
            [15, 30, 60],
            [
                "Short",
                "Moderate",
                "Long",
                "Very Long"
            ]
        )

        historical_queue_state = self._categorize(
            historical_queue_length,
            [10, 20],
            ["Low", "Medium", "High"]
        )

        arrival_period = self._arrival_period(
            arrival_hour
        )


        # --------------------------------------------------------
        # Evidence dictionary
        # --------------------------------------------------------

        evidence = {
            "congestion_state": congestion_state,
            "patients_ahead_state": patients_state,
            "queue_length_state": queue_state,
            "doctor_status": doctor_status,
            "doctor_delay_state": doctor_delay_state,
            "historical_wait_state": historical_wait_state,
            "historical_queue_state": historical_queue_state,
            "arrival_period": arrival_period
        }


        # --------------------------------------------------------
        # Calculate posterior for each waiting state
        # --------------------------------------------------------

        posterior_scores = {}


        for state in [
            "Short",
            "Moderate",
            "Long",
            "Very Long"
        ]:

            probability = self.priors[state]


            # -----------------------------------------------
            # Apply evidence probabilities
            # -----------------------------------------------

            for feature, value in evidence.items():

                likelihood = (
                    self._conditional_probability(
                        feature,
                        value,
                        state
                    )
                )

                probability *= likelihood


            posterior_scores[state] = probability


        # --------------------------------------------------------
        # Normalize posterior probabilities
        # --------------------------------------------------------

        total_probability = sum(
            posterior_scores.values()
        )


        if total_probability == 0:

            posterior_probabilities = {
                state: self.priors[state]
                for state in posterior_scores
            }

        else:

            posterior_probabilities = {
                state:
                probability / total_probability
                for state, probability
                in posterior_scores.items()
            }


        # --------------------------------------------------------
        # Most likely waiting state
        # --------------------------------------------------------

        predicted_state = max(
            posterior_probabilities,
            key=posterior_probabilities.get
        )


        predicted_probability = (
            posterior_probabilities[
                predicted_state
            ]
        )


        # --------------------------------------------------------
        # Convert state probabilities into expected minutes
        # --------------------------------------------------------

        state_midpoints = {
            "Short": 7.5,
            "Moderate": 23.0,
            "Long": 45.0,
            "Very Long": 75.0
        }


        expected_wait = sum(
            posterior_probabilities[state]
            * state_midpoints[state]
            for state in posterior_probabilities
        )


        return {
            "posterior_probabilities":
                posterior_probabilities,

            "predicted_state":
                predicted_state,

            "predicted_probability":
                float(
                    predicted_probability
                ),

            "expected_wait_minutes":
                float(
                    expected_wait
                ),

            "evidence":
                evidence
        }


    # ============================================================
    # CONDITIONAL PROBABILITY
    # ============================================================

    def _conditional_probability(
        self,
        feature,
        value,
        waiting_state
    ):

        state_df = self.df[
            self.df["waiting_state"]
            == waiting_state
        ]


        if len(state_df) == 0:
            return 1e-6


        matching_cases = (
            state_df[feature]
            == value
        ).sum()


        # Laplace smoothing
        #
        # Prevents zero probability when
        # a combination has not appeared
        # in the training data.

        unique_values = (
            self.df[feature]
            .nunique()
        )


        probability = (
            matching_cases + 1
        ) / (
            len(state_df)
            + unique_values
        )


        return float(
            probability
        )


    # ============================================================
    # CATEGORIZATION
    # ============================================================

    @staticmethod
    def _categorize(
        value,
        thresholds,
        labels
    ):

        if value <= thresholds[0]:

            return labels[0]

        elif value <= thresholds[1]:

            return labels[1]

        if len(thresholds) == 2:

            return labels[2]

        elif value <= thresholds[2]:

            return labels[2]

        else:

            return labels[3]


    # ============================================================
    # ARRIVAL PERIOD
    # ============================================================

    @staticmethod
    def _arrival_period(
        hour
    ):

        if hour <= 11:

            return "Morning"

        elif hour <= 15:

            return "Afternoon"

        elif hour <= 19:

            return "Evening"

        else:

            return "Night"


    # ============================================================
    # SUMMARY
    # ============================================================

    def summary(self):

        print(
            "==================================="
        )

        print(
            "FOUR-STATE BAYESIAN WAITING-TIME MODEL"
        )

        print(
            "==================================="
        )


        print(
            "\nWaiting-time states"
        )

        print(
            "-----------------------------------"
        )


        for state in [
            "Short",
            "Moderate",
            "Long",
            "Very Long"
        ]:

            print(
                f"{state:10} : "
                f"{self.priors[state]:.4f} "
                f"({self.priors[state] * 100:.2f}%)"
            )


# ================================================================
# MAIN TEST
# ================================================================

if __name__ == "__main__":

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


    # ------------------------------------------------------------
    # Load dataset
    # ------------------------------------------------------------

    df = pd.read_csv(
        DATASET_PATH
    )


    # ------------------------------------------------------------
    # Create Bayesian updater
    # ------------------------------------------------------------

    updater = BayesianWaitingTimeUpdater(
        df
    )


    # ------------------------------------------------------------
    # Display summary
    # ------------------------------------------------------------

    updater.summary()


    # ------------------------------------------------------------
    # Example patient
    # ------------------------------------------------------------

    patient_result = updater.predict(

        queue_congestion=0.82,

        patients_ahead=15,

        queue_length=25,

        doctor_available=0,

        doctor_delay_minutes=12,

        historical_average_wait=40,

        historical_queue_length=18,

        arrival_hour=14
    )


    # ------------------------------------------------------------
    # Display prediction
    # ------------------------------------------------------------

    print(
        "\nPatient Bayesian Prediction"
    )

    print(
        "-----------------------------------"
    )


    print(
        "\nPosterior probabilities:"
    )


    for state, probability in (
        patient_result[
            "posterior_probabilities"
        ].items()
    ):

        print(
            f"{state:10} : "
            f"{probability:.4f} "
            f"({probability * 100:.2f}%)"
        )


    print(
        "\nMost likely state:"
    )

    print(
        patient_result[
            "predicted_state"
        ]
    )


    print(
        "\nState probability:"
    )

    print(
        f"{patient_result['predicted_probability']:.4f}"
        f" "
        f"({patient_result['predicted_probability'] * 100:.2f}%)"
    )


    print(
        "\nExpected waiting time:"
    )

    print(
        f"{patient_result['expected_wait_minutes']:.2f} minutes"
    )


    print(
        "\nEvidence:"
    )

    for feature, value in (
        patient_result[
            "evidence"
        ].items()
    ):

        print(
            f"{feature:25} : {value}"
        )


    print(
        "\n==================================="
    )

    print(
        "FOUR-STATE BAYESIAN MODEL COMPLETED"
    )

    print(
        "==================================="
    )