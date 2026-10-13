import os
import pandas as pd


# --------------------------------------------------
# Dataset path
# --------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATASET_PATH = os.path.join(
    BASE_DIR,
    "datasets",
    "consultations.csv"
)


# --------------------------------------------------
# Load dataset
# --------------------------------------------------

df = pd.read_csv(DATASET_PATH)

THRESHOLD = 45
CONGESTION_THRESHOLD = 0.50


# --------------------------------------------------
# Define hypothesis and evidence
# --------------------------------------------------

df["H"] = df["waiting_time_minutes"] > THRESHOLD

df["High_Congestion"] = (
    df["queue_congestion"] > CONGESTION_THRESHOLD
)

df["Doctor_Unavailable"] = (
    df["doctor_available"] == 0
)


# --------------------------------------------------
# Helper function
# --------------------------------------------------

def probability(condition):
    return condition.mean()


# --------------------------------------------------
# Calculate probabilities
# --------------------------------------------------

overall_probability = probability(df["H"])

high_congestion_probability = probability(
    df.loc[df["High_Congestion"], "H"]
)

doctor_unavailable_probability = probability(
    df.loc[df["Doctor_Unavailable"], "H"]
)

both_probability = probability(
    df.loc[
        df["High_Congestion"] &
        df["Doctor_Unavailable"],
        "H"
    ]
)


# --------------------------------------------------
# Counts
# --------------------------------------------------

high_congestion_cases = df["High_Congestion"].sum()

doctor_unavailable_cases = df["Doctor_Unavailable"].sum()

both_cases = (
    df["High_Congestion"] &
    df["Doctor_Unavailable"]
).sum()


# --------------------------------------------------
# Output
# --------------------------------------------------

print("===================================")
print("PHASE 8.2 - MULTIPLE EVIDENCE")
print("===================================")

print(f"Total cases: {len(df)}")
print(f"Threshold: {THRESHOLD} minutes")
print(
    f"High congestion: > {CONGESTION_THRESHOLD}"
)


print("\nProbability comparison")
print("----------------------")

print(
    f"Overall P(W > 45)              : "
    f"{overall_probability:.4f} "
    f"({overall_probability * 100:.2f}%)"
)

print(
    f"High congestion                : "
    f"{high_congestion_probability:.4f} "
    f"({high_congestion_probability * 100:.2f}%)"
)

print(
    f"Doctor unavailable             : "
    f"{doctor_unavailable_probability:.4f} "
    f"({doctor_unavailable_probability * 100:.2f}%)"
)

print(
    f"High congestion + unavailable  : "
    f"{both_probability:.4f} "
    f"({both_probability * 100:.2f}%)"
)


print("\nCase counts")
print("----------------------")

print(
    f"High congestion cases         : "
    f"{high_congestion_cases}"
)

print(
    f"Doctor unavailable cases      : "
    f"{doctor_unavailable_cases}"
)

print(
    f"Both conditions               : "
    f"{both_cases}"
)


# --------------------------------------------------
# Conditional comparison
# --------------------------------------------------

print("\nAdditional evidence effect")
print("---------------------------")

print(
    f"Increase from overall to "
    f"high congestion: "
    f"{(
        high_congestion_probability
        - overall_probability
    ) * 100:.2f} percentage points"
)

print(
    f"Increase from high congestion "
    f"to both conditions: "
    f"{(
        both_probability
        - high_congestion_probability
    ) * 100:.2f} percentage points"
)


print("\n===================================")
print("MULTIPLE EVIDENCE ANALYSIS COMPLETED")
print("===================================")