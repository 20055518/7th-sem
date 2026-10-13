import pandas as pd
import joblib
from pathlib import Path

from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


# =========================
# 1. PATHS
# =========================

BASE_DIR = Path(__file__).resolve().parents[1]

DATA_PATH = BASE_DIR / "datasets" / "hospital_queue_dataset_5000.csv"
PREPROCESSOR_PATH = BASE_DIR / "models" / "preprocessor.pkl"
MODEL_PATH = BASE_DIR / "models" / "linear_regression.pkl"


# =========================
# 2. LOAD DATA
# =========================

df = pd.read_csv(DATA_PATH)

TARGET = "waiting_time_minutes"

X = df.drop(columns=[TARGET, "case_id", "queue_position"])
y = df[TARGET]


# =========================
# 3. TRAIN / TEST SPLIT
# =========================

from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42
)


# =========================
# 4. LOAD PREPROCESSOR
# =========================

preprocessor = joblib.load(PREPROCESSOR_PATH)

X_train_processed = preprocessor.transform(X_train)
X_test_processed = preprocessor.transform(X_test)


# =========================
# 5. TRAIN LINEAR REGRESSION
# =========================

model = LinearRegression()

model.fit(X_train_processed, y_train)


# =========================
# 6. PREDICTION
# =========================

y_pred = model.predict(X_test_processed)


# =========================
# 7. EVALUATION
# =========================

mae = mean_absolute_error(y_test, y_pred)

rmse = mean_squared_error(
    y_test,
    y_pred
) ** 0.5

r2 = r2_score(y_test, y_pred)


print("\n==============================")
print("LINEAR REGRESSION RESULTS")
print("==============================")

print(f"MAE  : {mae:.2f} minutes")
print(f"RMSE : {rmse:.2f} minutes")
print(f"R²   : {r2:.4f}")


# =========================
# 8. SAVE MODEL
# =========================

joblib.dump(model, MODEL_PATH)

print("\nModel saved successfully:")
print(MODEL_PATH)