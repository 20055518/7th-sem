import os
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

THRESHOLD = 30
CONGESTION_THRESHOLD = 0.60
PATIENTS_AHEAD_THRESHOLD = 10


# ============================================================
# DATASET PATH
# ============================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
print("BAYESIAN ANALYSIS")
print("===================================")

print(f"Total cases: {len(df)}")


# ============================================================
# CREATE HYPOTHESIS
# ============================================================

# H = Long or Very Long waiting time
df["H"] = df["waiting_time_minutes"] > THRESHOLD


# ============================================================
# CREATE EVIDENCE
# ============================================================

df["high_congestion"] = (
    df["queue_congestion"] > CONGESTION_THRESHOLD
)

df["doctor_unavailable"] = (
    df["doctor_available"] == 0
)

df["many_patients_ahead"] = (
    df["patients_ahead"] > PATIENTS_AHEAD_THRESHOLD
)


# Combined evidence:
# High congestion AND doctor unavailable
# AND many patients ahead

df["E"] = (
    df["high_congestion"]
    &
    df["doctor_unavailable"]
    &
    df["many_patients_ahead"]
)


# ============================================================
# BASIC COUNTS
# ============================================================

total_cases = len(df)

H_cases = df["H"].sum()
not_H_cases = (~df["H"]).sum()

E_cases = df["E"].sum()

H_and_E = (
    df["H"] & df["E"]
).sum()

not_H_and_E = (
    (~df["H"]) & df["E"]
).sum()


# ============================================================
# PRIOR PROBABILITIES
# ============================================================

P_H = H_cases / total_cases
P_not_H = not_H_cases / total_cases


# ============================================================
# LIKELIHOODS
# ============================================================

P_E_given_H = (
    H_and_E / H_cases
    if H_cases > 0 else 0
)

P_E_given_not_H = (
    not_H_and_E / not_H_cases
    if not_H_cases > 0 else 0
)


# ============================================================
# BAYESIAN UPDATE
# ============================================================

numerator = (
    P_E_given_H * P_H
)

denominator = (
    P_E_given_H * P_H
    +
    P_E_given_not_H * P_not_H
)

if denominator > 0:
    P_H_given_E = numerator / denominator
else:
    P_H_given_E = 0.0


# ============================================================
# WAITING-TIME STATE DISTRIBUTION
# ============================================================

def waiting_state(wait):

    if wait <= 15:
        return "Short"

    elif wait <= 30:
        return "Moderate"

    elif wait <= 60:
        return "Long"

    else:
        return "Very Long"


df["waiting_state"] = (
    df["waiting_time_minutes"]
    .apply(waiting_state)
)


state_counts = df["waiting_state"].value_counts()


# ============================================================
# OUTPUT
# ============================================================

print("\nHypothesis")
print("-----------------------------------")
print("H = Waiting time > 30 minutes")


print("\nEvidence")
print("-----------------------------------")
print("E = High congestion AND")
print("    Doctor unavailable AND")
print("    More than 10 patients ahead")


print("\nPrior probabilities")
print("-----------------------------------")
print(f"P(H)      = {P_H:.4f}")
print(f"P(~H)     = {P_not_H:.4f}")


print("\nLikelihoods")
print("-----------------------------------")
print(f"P(E | H)  = {P_E_given_H:.4f}")
print(f"P(E | ~H) = {P_E_given_not_H:.4f}")


print("\nBayesian posterior")
print("-----------------------------------")
print(f"P(H | E)  = {P_H_given_E:.4f}")
print(
    f"Posterior = {P_H_given_E * 100:.2f}%"
)


print("\nWaiting-time states")
print("-----------------------------------")

for state in ["Short", "Moderate", "Long", "Very Long"]:

    count = state_counts.get(state, 0)

    percentage = (
        count / total_cases * 100
    )

    print(
        f"{state:10} : "
        f"{count:4} "
        f"({percentage:.2f}%)"
    )


print("\nEvidence counts")
print("-----------------------------------")
print(f"High congestion             : {df['high_congestion'].sum()}")
print(f"Doctor unavailable          : {df['doctor_unavailable'].sum()}")
print(f"Many patients ahead         : {df['many_patients_ahead'].sum()}")
print(f"All evidence conditions     : {E_cases}")
print(f"Evidence + H                : {H_and_E}")
print(f"Evidence + ~H               : {not_H_and_E}")


print("\n===================================")
print("BAYESIAN ANALYSIS COMPLETED")
print("===================================")