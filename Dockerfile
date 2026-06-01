
FROM python:3.11-slim

# System deps (for LightGBM & SHAP compilation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Create necessary directories
RUN mkdir -p data models sql

# Environment defaults (overridden by docker-compose / .env)
ENV FLASK_HOST=0.0.0.0 \
    FLASK_PORT=5000 \
    FLASK_DEBUG=false \
    DATA_DIR=/app/data \
    MODELS_DIR=/app/models \
    DB_PATH=/app/sql/credit_risk.db \
    LLM_PROVIDER=gemini \
    LLM_MODEL=gemini-1.5-flash

EXPOSE 5000

# Entrypoint: run setup scripts if DB / model not present, then start server
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
