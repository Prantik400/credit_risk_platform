"""
docker_utils.py – Docker and data path utilities.

Helpers for resolving paths correctly whether running inside a Docker
container or in a local dev environment.
"""

import os
import sys
import subprocess
from src.utils.logger import get_logger

logger = get_logger(__name__)


def is_docker() -> bool:
    """Detect if we are running inside a Docker container."""
    return (
        os.path.exists("/.dockerenv")
        or os.environ.get("DOCKER_CONTAINER", "").lower() == "true"
    )


def resolve_data_path(filename: str) -> str:
    """
    Return the absolute path for a data file, checking both the
    configured DATA_DIR and common fallback locations.
    """
    from src.utils.config import DATA_DIR

    candidates = [
        os.path.join(DATA_DIR, filename),
        os.path.join("/app/data", filename),
        os.path.join(os.getcwd(), "data", filename),
        os.path.join(os.path.dirname(sys.argv[0]), "data", filename),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        f"{filename} not found. Searched:\n" + "\n".join(f"  {p}" for p in candidates)
    )


def check_data_files() -> dict:
    """
    Check which Home Credit dataset files are present.
    Returns a dict of filename → bool.
    """
    files = [
        "application_train.csv",
        "application_test.csv",
        "bureau.csv",
        "bureau_balance.csv",
        "previous_application.csv",
        "installments_payments.csv",
        "POS_CASH_balance.csv",
        "credit_card_balance.csv",
    ]
    from src.utils.config import DATA_DIR
    return {f: os.path.exists(os.path.join(DATA_DIR, f)) for f in files}


def check_model_files() -> dict:
    """Return which model artefacts are present."""
    from src.utils.config import MODELS_DIR
    files = [
        "lgbm_model.pkl",
        "preprocessor.pkl",
        "metadata.json",
        "shap_importance.csv",
        "business_rules.json",
    ]
    return {f: os.path.exists(os.path.join(MODELS_DIR, f)) for f in files}


def print_system_report():
    """Print a quick system-readiness report to stdout."""
    data_status  = check_data_files()
    model_status = check_model_files()

    print("\n══════════════════════════════════════════")
    print("  NeoStats System Status")
    print("══════════════════════════════════════════")
    print(f"  Environment  : {'Docker' if is_docker() else 'Local'}")
    print(f"  Python       : {sys.version.split()[0]}")

    print("\n  Data Files:")
    for fname, present in data_status.items():
        icon = "✓" if present else "✗"
        print(f"    {icon} {fname}")

    print("\n  Model Artefacts:")
    for fname, present in model_status.items():
        icon = "✓" if present else "✗"
        print(f"    {icon} {fname}")

    print("══════════════════════════════════════════\n")


if __name__ == "__main__":
    print_system_report()
