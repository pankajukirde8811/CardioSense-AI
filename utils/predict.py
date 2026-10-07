"""Load the trained model and turn user input into a heart-risk result."""
from pathlib import Path
import joblib
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "models" / "cardio_rf.joblib"

_bundle = joblib.load(MODEL_PATH)
MODEL = _bundle["model"]
FEATURES = _bundle["features"]


def cholesterol_level(mg_dl: float) -> int:
    """Convert mg/dl from a blood report to the dataset's 1/2/3 scale."""
    if mg_dl < 200:
        return 1
    if mg_dl < 240:
        return 2
    return 3


def glucose_level(mg_dl: float) -> int:
    """Convert fasting glucose mg/dl to the dataset's 1/2/3 scale."""
    if mg_dl < 100:
        return 1
    if mg_dl < 126:
        return 2
    return 3


def risk_label(percent: float) -> str:
    if percent < 30:
        return "Low"
    if percent < 50:
        return "Moderate"
    if percent < 70:
        return "Moderate–High"
    return "High"


def predict_risk(age, gender, height_cm, weight_kg, systolic, diastolic,
                 cholesterol_mg, glucose_mg, smoke, alcohol, active):
    """Return the risk %, the label, and the main warning flags."""
    bmi = weight_kg / (height_cm / 100) ** 2
    row = pd.DataFrame([{
        "age_years": age,
        "gender": 2 if gender == "male" else 1,
        "ap_hi": systolic,
        "ap_lo": diastolic,
        "cholesterol": cholesterol_level(cholesterol_mg),
        "gluc": glucose_level(glucose_mg),
        "smoke": int(smoke),
        "alco": int(alcohol),
        "active": int(active),
        "bmi": bmi,
    }])[FEATURES]

    percent = round(float(MODEL.predict_proba(row)[0][1]) * 100, 1)

    flags = []
    if systolic >= 140 or diastolic >= 90:
        flags.append("Elevated BP")
    if cholesterol_mg >= 240:
        flags.append("High cholesterol")
    if glucose_mg >= 126:
        flags.append("High glucose")
    if bmi >= 30:
        flags.append("Obesity (BMI ≥ 30)")
    if smoke:
        flags.append("Smoker")
    if not active:
        flags.append("Low physical activity")

    return {"risk": percent, "label": risk_label(percent),
            "bmi": round(bmi, 1), "flags": flags}