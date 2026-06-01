import os
import sys
import argparse
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.logger import get_logger
from src.utils.docker_utils import print_system_report

logger = get_logger("setup_all")


def run_setup(sample=None):
    t0 = time.time()
    print("\n" + "═"*55)
    print("  NeoStats Credit Risk — Full Setup Pipeline")
    print("═"*55)

    # 1: Build DB 
    from src.utils.config import DB_PATH
    if os.path.exists(DB_PATH):
        logger.info("Database already exists, skipping build")
    else:
        logger.info("Building SQLite database...")
        from scripts.build_db import build_db
        build_db(sample=sample)

    # 2: Model training
    from src.utils.config import MODELS_DIR
    from src.utils.helpers import model_is_trained
    if model_is_trained(MODELS_DIR):
        logger.info("Model already trained, skipping")
    else:
        logger.info("Training LightGBM model...")
        from src.ml.train import train
        meta = train()
        logger.info(f"  → OOF AUC: {meta['oof_auc']}  |  OOF AP: {meta['oof_ap']}")

    # 3: Risk scores 
    logger.info("Backfilling risk scores into DB...")
    from scripts.update_risk_scores import update
    update(sample=sample)

    # 4: Derive rules
    rules_path = os.path.join(MODELS_DIR, "business_rules.json")
    if os.path.exists(rules_path):
        logger.info("Rules already derived, skipping")
    else:
        logger.info("Deriving business rules...")
        from src.ml.rules import generate_and_save_rules
        generate_and_save_rules(sample_size=min(sample or 10_000, 10_000))

    elapsed = time.time() - t0
    print(f"\n Setup complete in {elapsed:.1f}s")
    print("  Start the server with:  python app.py")
    print("  Or with Docker:         docker-compose up --build\n")

    print_system_report()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=None,
                        help="Rows to sample (default=None=full dataset)")
    args = parser.parse_args()
    run_setup(sample=args.sample)
