import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
import joblib
from pathlib import Path


# =========================
# 1. PATHS
# =========================

BASE_DIR = Path(__file__).resolve().parents[1]

DATA_PATH = BASE_DIR / "datasets" / "hospital_queue_dataset_5000.csv"
MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True)


# =========================
# 2. LOAD DATA
# =========================

df = pd.read_csv(DATA_PATH)

print("Dataset loaded successfully")
print("Rows:", len(df))
print("Columns:", len(df.columns))


# =========================
# 3. BASIC VALIDATION
# =========================

print("\nMissing values:")
print(df.isnull().sum().sum())

print("\nDuplicate case IDs:")
print(df["case_id"].duplicated().sum())


# =========================
# 4. TARGET
# =========================

TARGET = "waiting_time_minutes"

X = df.drop(columns=[TARGET])
y = df[TARGET]


# =========================
# 5. REMOVE NON-ML COLUMNS
# =========================

X = X.drop(columns=[
    "case_id",
    "queue_position"
])


# =========================
# 6. COLUMN TYPES
# =========================

numerical_features = [
    "time_step",
    "patients_ahead",
    "queue_length",
    "queue_congestion",
    "doctor_available",
    "doctor_delay_minutes",
    "average_consultation_minutes",
    "completed_patients",
    "historical_average_wait",
    "historical_queue_length",
    "arrival_hour",
    "no_show_probability"
]

categorical_features = [
    "doctor_id",
    "department",
    "patient_type",
    "priority_level",
    "appointment_type",
    "day_of_week"
]


# =========================
# 7. PREPROCESSING
# =========================

numerical_pipeline = Pipeline([
    ("imputer", SimpleImputer(strategy="median")),
    ("scaler", StandardScaler())
])

categorical_pipeline = Pipeline([
    ("imputer", SimpleImputer(strategy="most_frequent")),
    ("encoder", OneHotEncoder(handle_unknown="ignore"))
])

preprocessor = ColumnTransformer([
    ("num", numerical_pipeline, numerical_features),
    ("cat", categorical_pipeline, categorical_features)
])


# =========================
# 8. TRAIN / TEST SPLIT
# =========================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42
)


print("\nTrain samples:", len(X_train))
print("Test samples:", len(X_test))


# =========================
# 9. FIT PREPROCESSOR
# =========================

preprocessor.fit(X_train)


# =========================
# 10. TRANSFORM DATA
# =========================

X_train_processed = preprocessor.transform(X_train)
X_test_processed = preprocessor.transform(X_test)


print("\nPreprocessing completed")
print("Processed training shape:", X_train_processed.shape)
print("Processed testing shape:", X_test_processed.shape)


# =========================
# 11. SAVE PREPROCESSOR
# =========================

preprocessor_path = MODEL_DIR / "preprocessor.pkl"

joblib.dump(
    preprocessor,
    preprocessor_path
)

print("\nPreprocessor saved to:")
print(preprocessor_path)