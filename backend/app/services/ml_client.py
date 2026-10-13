import httpx

from app.config import get_settings


# ============================================================
# ML API CONFIGURATION
# ============================================================

settings = get_settings()


# ============================================================
# CALL ML PREDICTION API
# ============================================================

async def predict_waiting_time(input_data: dict) -> dict:
    """
    Send queue information to the ML API and return the
    waiting-time and Bayesian probability predictions.

    Queue workflow is controlled by the main backend. This
    client only communicates with the prediction service.
    """
    if not isinstance(input_data, dict):
        raise TypeError("input_data must be a dictionary.")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                settings.ml_api_url,
                json=input_data,
            )
            response.raise_for_status()
            result = response.json()

    except httpx.TimeoutException as exc:
        raise RuntimeError("ML prediction service timed out.") from exc
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"ML prediction service returned HTTP {exc.response.status_code}."
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(
            "Unable to connect to the ML prediction service."
        ) from exc
    except ValueError as exc:
        raise RuntimeError(
            "ML prediction service returned invalid JSON."
        ) from exc

    if not isinstance(result, dict):
        raise RuntimeError("ML API returned an invalid response.")

    if result.get("success") is not True:
        raise RuntimeError("ML API returned an unsuccessful response.")

    prediction = result.get("prediction")
    if not isinstance(prediction, dict):
        raise RuntimeError(
            "ML API response does not contain a valid prediction."
        )

    return prediction
