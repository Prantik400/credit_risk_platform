
import os
import json
import pickle
import numpy as np
import pandas as pd
import shap
from functools import lru_cache

from src.utils.logger import get_logger
from src.utils.config import MODELS_DIR

logger = get_logger(__name__)

RISK_BANDS = [
    (0.00, 0.30, "Low",    "#22c55e"),   # green
    (0.30, 0.60, "Medium", "#f59e0b"),   # amber
    (0.60, 1.00, "High",   "#ef4444"),   # red
]


@lru_cache(maxsize=1)
def _load_artifacts():
    """Load model + preprocessor + metadata once and cache."""
    model_path = os.path.join(MODELS_DIR, "lgbm_model.pkl")
    prep_path  = os.path.join(MODELS_DIR, "preprocessor.pkl")
    meta_path  = os.path.join(MODELS_DIR, "metadata.json")

    with open(model_path, "rb") as f:
        model = pickle.load(f)
    with open(prep_path, "rb") as f:
        preprocessor = pickle.load(f)
    with open(meta_path) as f:
        meta = json.load(f)

    explainer = shap.TreeExplainer(model)
    logger.info("Model artefacts loaded and cached")
    return model, preprocessor, meta, explainer


def _get_band(prob: float) -> tuple[str, str]:
    for lo, hi, label, color in RISK_BANDS:
        if lo <= prob < hi or (prob >= hi and hi == 1.00):
            return label, color
    return "High", "#ef4444"


def predict_single(input_dict: dict) -> dict:
  
    model, preprocessor, meta, explainer = _load_artifacts()
    threshold = meta["best_threshold"]

    # Default values for every possible field 
    defaults = {
        "AMT_INCOME_TOTAL":            270000,
        "AMT_CREDIT":                  500000,
        "AMT_ANNUITY":                 25000,
        "AMT_GOODS_PRICE":             450000,
        "DAYS_BIRTH":                  -12775,   # ~35 years
        "DAYS_EMPLOYED":               -1825,    # ~5 years
        "DAYS_REGISTRATION":           -3000,
        "DAYS_ID_PUBLISH":             -2000,
        "REGION_POPULATION_RELATIVE":  0.02,
        "CNT_FAM_MEMBERS":             2,
        "CNT_CHILDREN":                0,
        "EXT_SOURCE_1":                0.5,
        "EXT_SOURCE_2":                0.5,
        "EXT_SOURCE_3":                0.5,
        "CODE_GENDER":                 "M",
        "NAME_CONTRACT_TYPE":          "Cash loans",
        "FLAG_OWN_CAR":                "N",
        "FLAG_OWN_REALTY":             "Y",
        "NAME_TYPE_SUITE":             "Unaccompanied",
        "NAME_INCOME_TYPE":            "Working",
        "NAME_EDUCATION_TYPE":         "Secondary / secondary special",
        "NAME_FAMILY_STATUS":          "Married",
        "NAME_HOUSING_TYPE":           "House / apartment",
        "OCCUPATION_TYPE":             "Laborers",
        "WEEKDAY_APPR_PROCESS_START":  "TUESDAY",
        "ORGANIZATION_TYPE":           "Business Entity Type 3",
        # Bureau aggregates
        "BUREAU_LOAN_COUNT":           0,
        "BUREAU_ACTIVE_LOANS":         0,
        "BUREAU_AVG_DAYS_CREDIT":      0,
        "BUREAU_TOTAL_CREDIT_SUM":     0,
        "BUREAU_TOTAL_OVERDUE":        0,
        # Previous application aggregates
        "PREV_APP_COUNT":              0,
        "PREV_APPROVED_COUNT":         0,
        "PREV_REFUSED_COUNT":          0,
        "PREV_AVG_AMT_APPLICATION":    0,
        "PREV_AVG_AMT_CREDIT":         0,
    }

    # Merge: user input overrides defaults
    merged = {**defaults, **input_dict}

    # Build a one-row DataFrame
    row = pd.DataFrame([merged])

    # Preprocess
    X = preprocessor.transform(row)

    # Predict probability
    prob = float(model.predict_proba(X)[0, 1])
    band, color = _get_band(prob)

    # SHAP explanation
    shap_vals = explainer.shap_values(X)
    if isinstance(shap_vals, list):
        shap_vals = shap_vals[1]
    sv = shap_vals[0]
    feat_names = preprocessor.feature_names_

    shap_df = pd.DataFrame({
        "feature": feat_names,
        "value":   X.iloc[0].values,
        "shap":    sv,
    })
    shap_df["abs_shap"] = shap_df["shap"].abs()
    shap_df = shap_df.sort_values("abs_shap", ascending=False).head(10)

    top10 = []
    for _, r in shap_df.iterrows():
        top10.append({
            "feature":    r["feature"],
            "value":      round(float(r["value"]), 4),
            "shap_value": round(float(r["shap"]), 4),
            "direction":  "increases risk" if r["shap"] > 0 else "decreases risk",
        })

    return {
        "probability": round(prob, 4),
        "risk_score":  round(prob * 100, 1),
        "risk_band":   band,
        "band_color":  color,
        "threshold":   threshold,
        "decision":    "REJECT" if prob >= threshold else "APPROVE",
        "shap_top10":  top10,
    }


def predict_batch(df: pd.DataFrame) -> pd.DataFrame:
    """Score a DataFrame of applications."""
    model, preprocessor, meta, _ = _load_artifacts()
    threshold = meta["best_threshold"]
    X = preprocessor.transform(df)
    probs = model.predict_proba(X)[:, 1]
    bands = [_get_band(p)[0] for p in probs]
    df = df.copy()
    df["RISK_PROBABILITY"] = probs.round(4)
    df["RISK_SCORE"]  = (probs * 100).round(1)
    df["RISK_BAND"]   = bands
    df["DECISION"]    = ["REJECT" if p >= threshold else "APPROVE" for p in probs]
    return df