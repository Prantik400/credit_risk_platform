import os
import json
import sqlite3
import pandas as pd
from src.utils.logger import get_logger
from src.utils.config import DB_PATH

logger = get_logger(__name__)

MAX_ROWS = 500 


def get_connection() -> sqlite3.Connection:
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. "
            "Please run `python scripts/build_db.py` first."
        )
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def run_query(sql: str) -> tuple[pd.DataFrame, str]:
  
    try:
        conn = get_connection()
        df = pd.read_sql_query(sql, conn)
        conn.close()

        if len(df) > MAX_ROWS:
            df = df.head(MAX_ROWS)
            logger.info(f"Result truncated to {MAX_ROWS} rows")

        return df, ""
    except Exception as e:
        logger.error(f"Query error: {e}\nSQL: {sql}")
        return pd.DataFrame(), str(e)


def df_to_json(df: pd.DataFrame, max_rows: int = 20) -> str:
   
    return df.head(max_rows).to_json(orient="records", default_handler=str)


def run_and_describe(sql: str) -> dict:
   
    df, error = run_query(sql)
    if error:
        return {"success": False, "error": error, "sql": sql}

    return {
        "success": True,
        "sql": sql,
        "row_count": len(df),
        "columns": list(df.columns),
        "data": df.head(MAX_ROWS).to_dict(orient="records"),
        "data_json": df_to_json(df),
        "truncated": len(df) == MAX_ROWS
    }
