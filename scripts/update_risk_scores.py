import os
import sys
import sqlite3
import argparse
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ml.predict import predict_batch
from src.utils.config import DB_PATH
from src.utils.logger import get_logger

logger = get_logger("update_risk_scores")


def update(sample: int | None = None):
    # Read directly from SQLite
    logger.info(f"Reading applicants from database...")
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT * FROM applications"
    if sample:
        query += f" LIMIT {sample}"
    df = pd.read_sql(query, conn)
    conn.close()

    logger.info(f"Scoring {len(df):,} applicants...")
    df_scored = predict_batch(df)

    logger.info("Writing risk scores back to database...")
    conn = sqlite3.connect(DB_PATH)
    conn.executemany(
        "UPDATE applications SET RISK_BAND=?, RISK_SCORE=? WHERE SK_ID_CURR=?",
        list(df_scored[["RISK_BAND", "RISK_SCORE", "SK_ID_CURR"]].itertuples(index=False, name=None)),
    )
    conn.commit()
    conn.close()
    logger.info("Risk scores updated in database")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=None)
    args = parser.parse_args()
    update(sample=args.sample)
