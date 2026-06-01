import os
import json
import pickle
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import (
    roc_auc_score, average_precision_score,
    f1_score, classification_report
)

import lightgbm as lgb
import shap

from src.data.loader import load_and_join
from src.data.preprocessor import CreditPreprocessor
from src.utils.logger import get_logger
from src.utils.config import MODELS_DIR, DATA_SAMPLE

logger = get_logger(__name__)

RANDOM_STATE = 42
N_SPLITS = 5

LGBM_PARAMS = {
    "objective": "binary",
    "metric": "auc",
    "learning_rate": 0.05,
    "n_estimators": 500,
    "num_leaves": 63,
    "max_depth": -1,
    "min_child_samples": 50,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 0.1,
    "class_weight": "balanced",
    "n_jobs": -1,
    "random_state": RANDOM_STATE,
    "verbose": -1,
}


def train():
    os.makedirs(MODELS_DIR, exist_ok=True)

    # 1. Load data
    logger.info("Loading dataset …")
    df = load_and_join(sample=DATA_SAMPLE)
    target = df["TARGET"]
    logger.info(f"Target distribution:\n{target.value_counts(normalize=True).round(3)}")

    # 2. Preprocess
    logger.info("Fitting preprocessor …")
    prep = CreditPreprocessor()
    X = prep.fit_transform(df)
    y = target.values

    feature_names = list(X.columns)
    logger.info(f"Feature matrix: {X.shape}")

    # 3. Cross-validation
    skf = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)
    oof_preds = np.zeros(len(y))
    fold_aucs = []

    logger.info(f"Starting {N_SPLITS}-fold stratified CV …")
    for fold, (tr_idx, val_idx) in enumerate(skf.split(X, y), 1):
        X_tr, X_val = X.iloc[tr_idx], X.iloc[val_idx]
        y_tr, y_val = y[tr_idx], y[val_idx]

        model = lgb.LGBMClassifier(**LGBM_PARAMS)
        model.fit(
            X_tr, y_tr,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(50, verbose=False),
                       lgb.log_evaluation(period=100)],
        )
        preds = model.predict_proba(X_val)[:, 1]
        oof_preds[val_idx] = preds
        auc = roc_auc_score(y_val, preds)
        fold_aucs.append(auc)
        logger.info(f"  Fold {fold}: AUC = {auc:.4f}")

    oof_auc = roc_auc_score(y, oof_preds)
    oof_ap  = average_precision_score(y, oof_preds)
    logger.info(f"OOF AUC = {oof_auc:.4f}  |  OOF AP = {oof_ap:.4f}")

    # 4. Final model on full data
    logger.info("Training final model on full data …")
    final_model = lgb.LGBMClassifier(**LGBM_PARAMS)
    final_model.fit(X, y)

    # 5. Threshold optimisation

    thresholds = np.linspace(0.1, 0.9, 81)
    f1s = [f1_score(y, (oof_preds >= t).astype(int)) for t in thresholds]
    best_threshold = float(thresholds[np.argmax(f1s)])
    best_f1 = float(max(f1s))
    logger.info(f"Best threshold: {best_threshold:.2f}  |  Best OOF F1: {best_f1:.4f}")

    y_pred_bin = (oof_preds >= best_threshold).astype(int)
    logger.info(f"\n{classification_report(y, y_pred_bin, target_names=['No Default','Default'])}")

    # 6. SHAP – compute on a sample for speed

    logger.info("Computing SHAP values (sample of 2000) …")
    sample_idx = np.random.RandomState(RANDOM_STATE).choice(len(X), size=min(2000, len(X)), replace=False)
    explainer = shap.TreeExplainer(final_model)
    shap_values = explainer.shap_values(X.iloc[sample_idx])
    # For binary classification lgb, shap_values may be list; take class-1
    if isinstance(shap_values, list):
        shap_values = shap_values[1]
    shap_importance = pd.DataFrame({
        "feature": feature_names,
        "mean_abs_shap": np.abs(shap_values).mean(axis=0),
    }).sort_values("mean_abs_shap", ascending=False)

    # 7. Save artefacts
    model_path = os.path.join(MODELS_DIR, "lgbm_model.pkl")
    prep_path  = os.path.join(MODELS_DIR, "preprocessor.pkl")
    meta_path  = os.path.join(MODELS_DIR, "metadata.json")
    shap_path  = os.path.join(MODELS_DIR, "shap_importance.csv")

    with open(model_path, "wb") as f:
        pickle.dump(final_model, f)
    with open(prep_path, "wb") as f:
        pickle.dump(prep, f)

    meta = {
        "oof_auc":       round(oof_auc, 4),
        "oof_ap":        round(oof_ap, 4),
        "best_threshold": best_threshold,
        "best_oof_f1":   round(best_f1, 4),
        "fold_aucs":     [round(a, 4) for a in fold_aucs],
        "n_features":    len(feature_names),
        "feature_names": feature_names,
        "n_train_rows":  int(len(y)),
        "default_rate":  round(float(y.mean()), 4),
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    shap_importance.to_csv(shap_path, index=False)

    logger.info(f"Model saved to {model_path}")
    logger.info(f"Preprocessor saved to {prep_path}")
    logger.info(f"Metadata saved to {meta_path}")
    logger.info("Training complete ✓")
    return meta


if __name__ == "__main__":
    train()
