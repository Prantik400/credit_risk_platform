"""helpers.py – Misc utility functions."""
import os
import json
import pickle
from datetime import datetime


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def safe_load_json(path: str, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def safe_load_pickle(path: str):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


def model_is_trained(models_dir: str) -> bool:
    required = ["lgbm_model.pkl", "preprocessor.pkl", "metadata.json"]
    return all(os.path.exists(os.path.join(models_dir, f)) for f in required)
