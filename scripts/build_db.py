
import os
import sys
import argparse
import sqlite3
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.loader import load_and_join
from src.utils.config import DB_PATH
from src.utils.logger import get_logger

logger = get_logger("build_db")


def build_db(sample: int | None = None):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    logger.info(f"Loading data (sample={sample}) …")
    df = load_and_join(sample=sample)

    # Add placeholder model
    if "RISK_BAND" not in df.columns:
        df["RISK_BAND"]  = None
        df["RISK_SCORE"] = None

    # Write to SQLite
    logger.info(f"Writing {len(df):,} rows to {DB_PATH} …")
    conn = sqlite3.connect(DB_PATH)

    # Drop & recreate
    conn.execute("DROP TABLE IF EXISTS applications")

    df.to_sql("applications", conn, index=False, if_exists="replace",
              chunksize=10_000)

    # Indexes for common filter columns
    for col in ["TARGET", "CODE_GENDER", "NAME_INCOME_TYPE",
                "NAME_EDUCATION_TYPE", "RISK_BAND"]:
        if col in df.columns:
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{col} ON applications({col})"
            )

    conn.commit()
    row_count = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
    conn.close()

    logger.info(f"Database built: {row_count:,} rows in `applications` table")
    logger.info(f"Location: {DB_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=None,
                        help="Rows to load (None = full dataset)")
    args = parser.parse_args()
    build_db(sample=args.sample)
