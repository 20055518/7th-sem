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

print("===================================")
print("DATASET VALIDATION")
print("===================================")

print(f"Rows: {len(df)}")
print(f"Columns: {len(df.columns)}")


# --------------------------------------------------
# Missing values
# --------------------------------------------------

print("\nMissing values:")
print(df.isnull().sum())


# --------------------------------------------------
# Duplicate rows
# --------------------------------------------------

print("\nDuplicate rows:")
print(df.duplicated().sum())


# --------------------------------------------------
# Target statistics
# --------------------------------------------------

target = "waiting_time_minutes"

print("\nTarget statistics:")
print(df[target].describe())


# --------------------------------------------------
# Numerical correlations
# --------------------------------------------------

print("\nCorrelation with waiting_time_minutes:")

numeric_columns = df.select_dtypes(
    include="number"
).columns

correlations = (
    df[numeric_columns]
    .corr()[target]
    .sort_values(ascending=False)
)

print(correlations)


# --------------------------------------------------
# Categorical feature distribution
# --------------------------------------------------

print("\nDay of week distribution:")
print(df["day_of_week"].value_counts())


# --------------------------------------------------
# Important feature ranges
# --------------------------------------------------

print("\nFeature ranges:")

for column in numeric_columns:
    print(
        f"{column}: "
        f"min={df[column].min():.3f}, "
        f"max={df[column].max():.3f}"
    )


# --------------------------------------------------
# Check relationship between target and
# important queue features
# --------------------------------------------------

print("\nSample of important variables:")

print(
    df[
        [
            "patients_ahead",
            "queue_length",
            "queue_congestion",
            "historical_average_wait",
            "waiting_time_minutes"
        ]
    ].head(10)
)

print("\n===================================")
print("VALIDATION COMPLETED")
print("===================================")