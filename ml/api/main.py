from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .predictor import predict_queue


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Hospital Queue ML API",
    description=(   
        "Machine Learning API for hospital waiting-time "
        "prediction and Bayesian waiting-state probability."
    ),
    version="1.0.0"
)


# ============================================================
# REQUEST MODEL
# ============================================================

class QueuePredictionRequest(BaseModel):

    time_step: int = Field(..., ge=0)

    queue_congestion: float = Field(
        ...,
        ge=0.0,
        le=1.0
    )

    patients_ahead: int = Field(
        ...,
        ge=0
    )

    queue_length: int = Field(
        ...,
        ge=0
    )

    doctor_available: int = Field(
        ...,
        ge=0,
        le=1
    )

    doctor_delay_minutes: float = Field(
        ...,
        ge=0
    )

    average_consultation_minutes: float = Field(
        ...,
        ge=0
    )

    completed_patients: int = Field(
        ...,
        ge=0
    )

    historical_average_wait: float = Field(
        ...,
        ge=0
    )

    historical_queue_length: int = Field(
        ...,
        ge=0
    )

    arrival_hour: int = Field(
        ...,
        ge=0,
        le=23
    )

    no_show_probability: float = Field(
        ...,
        ge=0.0,
        le=1.0
    )

    doctor_id: str
    department: str
    patient_type: str
    priority_level: str
    appointment_type: str
    day_of_week: str


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health_check():

    return {
        "status": "ok",
        "service": "Hospital Queue ML API",
        "version": "1.0.0"
    }


# ============================================================
# WAITING-TIME + BAYESIAN PREDICTION
# ============================================================

@app.post("/predict")
def predict(request: QueuePredictionRequest):

    try:

        input_data = request.model_dump()

        result = predict_queue(
            input_data
        )

        return {
            "success": True,
            "prediction": result
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )