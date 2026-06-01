
import os
import json
import pickle
import numpy as np
import pandas as pd
from sklearn.metrics import (
    roc_auc_score, average_precision_score, f1_score,
    precision_score, recall_score, confusion_matrix,
    roc_curve, precision_recall_curve,
)
from src.data.loader import load_and_join
from src.data.preprocessor import CreditPreprocessor
from src.utils.config import MODELS_DIR, DATA_SAMPLE
from src.utils.logger import get_logger

logger = get_logger(__name__)


def evaluate_on_holdout(test_size: float = 0.2) -> dict:
    from sklearn.model_selection import train_test_split

    df  = load_and_join(sample=DATA_SAMPLE)
    y   = df["TARGET"].values

    with open(os.path.join(MODELS_DIR, "preprocessor.pkl"), "rb") as f:
        prep = pickle.load(f)
    with open(os.path.join(MODELS_DIR, "lgbm_model.pkl"), "rb") as f:
        model = pickle.load(f)
    with open(os.path.join(MODELS_DIR, "metadata.json")) as f:
        meta = json.load(f)

    X = prep.transform(df)
    _, X_test, _, y_test = train_test_split(
        X, y, test_size=test_size, stratify=y, random_state=42
    )

    probs = model.predict_proba(X_test)[:, 1]
    threshold = meta["best_threshold"]
    preds = (probs >= threshold).astype(int)

    fpr, tpr, _ = roc_curve(y_test, probs)
    prec_curve, rec_curve, _ = precision_recall_curve(y_test, probs)
    cm = confusion_matrix(y_test, preds)

    metrics = {
        "roc_auc":   round(roc_auc_score(y_test, probs), 4),
        "pr_auc":    round(average_precision_score(y_test, probs), 4),
        "f1":        round(f1_score(y_test, preds), 4),
        "precision": round(precision_score(y_test, preds), 4),
        "recall":    round(recall_score(y_test, preds), 4),
        "threshold": threshold,
        "confusion_matrix": cm.tolist(),
        "roc_curve": {"fpr": fpr.tolist(), "tpr": tpr.tolist()},
        "pr_curve":  {"precision": prec_curve.tolist(), "recall": rec_curve.tolist()},
    }
    logger.info(f"Evaluation metrics: AUC={metrics['roc_auc']}, F1={metrics['f1']}")
    return metrics


def load_saved_metrics() -> dict:
    meta_path = os.path.join(MODELS_DIR, "metadata.json")
    if not os.path.exists(meta_path):
        return {}
    with open(meta_path) as f:
        return json.load(f)
