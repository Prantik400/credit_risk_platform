#!/bin/bash
set -e

echo "──────────────────────────────────────────"
echo "  NeoStats Credit Risk Platform"
echo "──────────────────────────────────────────"

# 1. Build SQLite DB (if not already built) 
if [ ! -f "${DB_PATH}" ]; then
  if [ -f "${DATA_DIR}/application_train.csv" ]; then
    echo "[setup] Building SQLite database from CSV files…"
    python scripts/build_db.py ${DATA_SAMPLE:+--sample $DATA_SAMPLE}
  else
    echo "[warn] application_train.csv not found in ${DATA_DIR}."
    echo "       Download from: https://www.kaggle.com/competitions/home-credit-default-risk/data"
    echo "       Place files in the ./data/ directory and restart the container."
  fi
fi

# 2. Train model 
if [ ! -f "${MODELS_DIR}/lgbm_model.pkl" ]; then
  if [ -f "${DATA_DIR}/application_train.csv" ]; then
    echo "[setup] Training model… (this may take several minutes)"
    python -c "from src.ml.train import train; train()"
    echo "[setup] Backfilling risk scores into DB…"
    python scripts/update_risk_scores.py ${DATA_SAMPLE:+--sample $DATA_SAMPLE}
  fi
fi

# 3. Start Flask server 
echo "[start] Starting Flask application on port ${FLASK_PORT}…"
exec gunicorn app:app \
  --bind ${FLASK_HOST}:${FLASK_PORT} \
  --workers 2 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
