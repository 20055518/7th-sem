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


print("===================================")
print("PHASE 7 - PROBABILITY ANALYSIS")
print("===================================")

print(f"Dataset rows: {len(df)}")
print(f"Waiting-time threshold: {THRESHOLD} minutes")


# --------------------------------------------------
# Create event
# --------------------------------------------------

df["wait_over_45"] = (
    df["waiting_time_minutes"] > THRESHOLD
)


# --------------------------------------------------
# Overall probability
# --------------------------------------------------

total_cases = len(df)

cases_over_45 = df["wait_over_45"].sum()

overall_probability = cases_over_45 / total_cases


print("\nOverall probability")
print("-------------------")

print(f"Cases above 45 minutes: {cases_over_45}")
print(f"Total cases: {total_cases}")
print(
    f"P(W > 45) = {overall_probability:.4f}"
)
print(
    f"Percentage = {overall_probability * 100:.2f}%"
)


# --------------------------------------------------
# Probability by queue congestion
# --------------------------------------------------

print("\nProbability by queue congestion")
print("--------------------------------")

df["congestion_group"] = pd.cut(
    df["queue_congestion"],
    bins=[-0.01, 0.25, 0.50, 0.75],
    labels=[
        "Low",
        "Medium",
        "High"
    ]
)

congestion_probability = (
    df.groupby(
        "congestion_group",
        observed=True
    )["wait_over_45"]
    .mean()
)

print(congestion_probability)


# --------------------------------------------------
# Probability by patients ahead
# --------------------------------------------------

print("\nProbability by patients ahead")
print("-----------------------------")

df["patients_ahead_group"] = pd.cut(
    df["patients_ahead"],
    bins=[-1, 5, 10, 15, 23],
    labels=[
        "0-5",
        "6-10",
        "11-15",
        "16-23"
    ]
)

patients_probability = (
    df.groupby(
        "patients_ahead_group",
        observed=True
    )["wait_over_45"]
    .mean()
)

print(patients_probability)


# --------------------------------------------------
# Probability by doctor availability
# --------------------------------------------------

print("\nProbability by doctor availability")
print("----------------------------------")

doctor_probability = (
    df.groupby("doctor_available")["wait_over_45"]
    .mean()
)

print(doctor_probability)


# --------------------------------------------------
# Summary
# --------------------------------------------------

print("\n===================================")
print("PROBABILITY ANALYSIS COMPLETED")
print("===================================")