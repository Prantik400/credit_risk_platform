import os
import json
import pickle
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.model_selection import train_test_split

from src.utils.config import MODELS_DIR
from src.utils.logger import get_logger

logger = get_logger(__name__)

RULES_PATH = os.path.join(MODELS_DIR, "business_rules.json")



# 1. Distilled Decision-Tree Rules

def _load_artifacts():
    with open(os.path.join(MODELS_DIR, "lgbm_model.pkl"), "rb") as f:
        model = pickle.load(f)
    with open(os.path.join(MODELS_DIR, "preprocessor.pkl"), "rb") as f:
        prep = pickle.load(f)
    with open(os.path.join(MODELS_DIR, "metadata.json")) as f:
        meta = json.load(f)
    return model, prep, meta


def derive_tree_rules(X: pd.DataFrame, y_prob: np.ndarray,
                      max_depth: int = 4) -> dict:

    threshold = 0.5
    y_bin = (y_prob >= threshold).astype(int)

    dt = DecisionTreeClassifier(
        max_depth=max_depth,
        min_samples_leaf=200,
        class_weight="balanced",
        random_state=42,
    )
    dt.fit(X, y_bin)

    tree_text = export_text(dt, feature_names=list(X.columns), max_depth=max_depth)
    feature_importance = dict(zip(X.columns, dt.feature_importances_))
    top_features = sorted(feature_importance.items(), key=lambda x: -x[1])[:10]

    return {
        "algorithm":    "Decision Tree (distilled from LightGBM)",
        "max_depth":    max_depth,
        "tree_text":    tree_text,
        "top_features": [{"feature": f, "importance": round(v, 4)} for f, v in top_features],
        "accuracy":     round(dt.score(X, y_bin), 4),
    }



# 2. Scorecard 

SCORECARD_RULES = [
    {
        "id": "R01",
        "name": "External Credit Score",
        "feature": "EXT_SOURCE_2",
        "condition": "< 0.35",
        "action": "FLAG HIGH RISK",
        "rationale": "External bureau score below 0.35 is strongly associated with default (>20% default rate in training data).",
        "weight": "HIGH",
    },
    {
        "id": "R02",
        "name": "Credit-to-Income Ratio",
        "feature": "CREDIT_TO_INCOME",
        "condition": "> 3.0",
        "action": "REQUIRE ADDITIONAL REVIEW",
        "rationale": "Loan amount exceeding 3× annual income significantly raises repayment risk.",
        "weight": "HIGH",
    },
    {
        "id": "R03",
        "name": "Annuity Burden",
        "feature": "ANNUITY_TO_INCOME",
        "condition": "> 0.40",
        "action": "FLAG HIGH RISK",
        "rationale": "Monthly annuity exceeding 40% of monthly income indicates over-leverage.",
        "weight": "HIGH",
    },
    {
        "id": "R04",
        "name": "Applicant Age",
        "feature": "AGE_YEARS",
        "condition": "< 27",
        "action": "REQUIRE GUARANTOR",
        "rationale": "Applicants under 27 default at nearly 2× the average rate in historical data.",
        "weight": "MEDIUM",
    },
    {
        "id": "R05",
        "name": "Employment Gap",
        "feature": "YEARS_EMPLOYED",
        "condition": "< 1",
        "action": "REQUIRE ADDITIONAL DOCUMENTS",
        "rationale": "Less than 1 year of employment history correlates with income instability.",
        "weight": "MEDIUM",
    },
    {
        "id": "R06",
        "name": "External Score Mean",
        "feature": "EXT_SOURCE_MEAN",
        "condition": "< 0.30",
        "action": "AUTO REJECT",
        "rationale": "Mean of all external scores below 0.30 indicates very high risk across all bureaus.",
        "weight": "CRITICAL",
    },
    {
        "id": "R07",
        "name": "Bureau Overdue Amount",
        "feature": "BUREAU_TOTAL_OVERDUE",
        "condition": "> 0",
        "action": "FLAG HIGH RISK",
        "rationale": "Any outstanding overdue bureau amount indicates prior repayment difficulties.",
        "weight": "HIGH",
    },
    {
        "id": "R08",
        "name": "Prior Loan Refusals",
        "feature": "PREV_REFUSED_COUNT",
        "condition": "> 1",
        "action": "REQUIRE ADDITIONAL REVIEW",
        "rationale": "More than 1 prior application refusal suggests systemic credit issues.",
        "weight": "MEDIUM",
    },
    {
        "id": "R09",
        "name": "Active Bureau Loans",
        "feature": "BUREAU_ACTIVE_LOANS",
        "condition": "> 5",
        "action": "REQUIRE ADDITIONAL REVIEW",
        "rationale": "More than 5 active bureau loans indicates high concurrent debt obligations.",
        "weight": "MEDIUM",
    },
    {
        "id": "R10",
        "name": "Income Verification",
        "feature": "AMT_INCOME_TOTAL",
        "condition": "< 54000",
        "action": "REQUIRE INCOME PROOF",
        "rationale": "Very low declared income (bottom 10th percentile) warrants income verification.",
        "weight": "LOW",
    },
]

# 3. Composite Risk engine rules

def apply_rules(applicant: dict) -> dict:
   
    triggered = []
    score = 0
    weight_map = {"CRITICAL": 40, "HIGH": 20, "MEDIUM": 10, "LOW": 5}

    feature_map = {
        "EXT_SOURCE_2":        float(applicant.get("EXT_SOURCE_2") or 0.5),
        "CREDIT_TO_INCOME":    float(applicant.get("AMT_CREDIT", 0)) /
                               max(float(applicant.get("AMT_INCOME_TOTAL", 1)), 1),
        "ANNUITY_TO_INCOME":   float(applicant.get("AMT_ANNUITY", 0)) /
                               max(float(applicant.get("AMT_INCOME_TOTAL", 1)), 1),
        "AGE_YEARS":           -float(applicant.get("DAYS_BIRTH", -35*365)) / 365,
        "YEARS_EMPLOYED":      -float(applicant.get("DAYS_EMPLOYED", -5*365)) / 365
                               if applicant.get("DAYS_EMPLOYED", 0) != 365243 else 0,
        "EXT_SOURCE_MEAN":     np.mean([
                                   float(applicant.get("EXT_SOURCE_1") or 0.5),
                                   float(applicant.get("EXT_SOURCE_2") or 0.5),
                                   float(applicant.get("EXT_SOURCE_3") or 0.5),
                               ]),
        "BUREAU_TOTAL_OVERDUE": float(applicant.get("BUREAU_TOTAL_OVERDUE", 0)),
        "PREV_REFUSED_COUNT":   float(applicant.get("PREV_REFUSED_COUNT", 0)),
        "BUREAU_ACTIVE_LOANS":  float(applicant.get("BUREAU_ACTIVE_LOANS", 0)),
        "AMT_INCOME_TOTAL":     float(applicant.get("AMT_INCOME_TOTAL", 0)),
    }

    evaluators = {
        "R01": lambda v: v["EXT_SOURCE_2"] < 0.35,
        "R02": lambda v: v["CREDIT_TO_INCOME"] > 3.0,
        "R03": lambda v: v["ANNUITY_TO_INCOME"] > 0.40,
        "R04": lambda v: v["AGE_YEARS"] < 27,
        "R05": lambda v: v["YEARS_EMPLOYED"] < 1,
        "R06": lambda v: v["EXT_SOURCE_MEAN"] < 0.30,
        "R07": lambda v: v["BUREAU_TOTAL_OVERDUE"] > 0,
        "R08": lambda v: v["PREV_REFUSED_COUNT"] > 1,
        "R09": lambda v: v["BUREAU_ACTIVE_LOANS"] > 5,
        "R10": lambda v: v["AMT_INCOME_TOTAL"] < 54000,
    }

    for rule in SCORECARD_RULES:
        try:
            if evaluators[rule["id"]](feature_map):
                triggered.append({
                    **rule,
                    "triggered": True,
                    "feature_value": round(feature_map.get(rule["feature"], 0), 4),
                })
                score += weight_map.get(rule["weight"], 0)
        except Exception:
            pass

    if score >= 40:
        recommendation = "AUTO REJECT"
        color = "#ef4444"
    elif score >= 20:
        recommendation = "MANUAL REVIEW REQUIRED"
        color = "#f59e0b"
    elif score >= 10:
        recommendation = "CONDITIONAL APPROVE"
        color = "#06b6d4"
    else:
        recommendation = "AUTO APPROVE"
        color = "#22c55e"

    return {
        "triggered_rules":   triggered,
        "rules_score":       score,
        "recommendation":    recommendation,
        "recommendation_color": color,
        "total_rules":       len(SCORECARD_RULES),
        "triggered_count":   len(triggered),
    }

# 4. Generate & Save Rules Report

def generate_and_save_rules(sample_size: int = 10_000):
    from src.data.loader import load_and_join

    logger.info("Loading data for rule derivation…")
    df = load_and_join(sample=sample_size)

    model, prep, meta = _load_artifacts()
    X = prep.transform(df)
    y_prob = model.predict_proba(X)[:, 1]

    logger.info("Deriving decision tree rules…")
    tree_rules = derive_tree_rules(X, y_prob, max_depth=4)

    output = {
        "scorecard_rules": SCORECARD_RULES,
        "distilled_tree":  tree_rules,
        "sample_size":     sample_size,
    }

    os.makedirs(MODELS_DIR, exist_ok=True)
    with open(RULES_PATH, "w") as f:
        json.dump(output, f, indent=2)

    logger.info(f"Rules saved to {RULES_PATH}")
    return output


def load_rules() -> dict:
    """Load pre-generated rules, or return scorecard rules as fallback."""
    if os.path.exists(RULES_PATH):
        with open(RULES_PATH) as f:
            return json.load(f)
    return {"scorecard_rules": SCORECARD_RULES, "distilled_tree": None}
