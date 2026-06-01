# NeoStats · AI-Powered Credit Risk Intelligence Platform

> **Candidate Assignment — AI Engineer Role**  
> A full-stack credit risk platform: EDA → ML model → Explainable AI → Conversational Data Interface → Dockerized Deployment.

---

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Quick Start (Docker)](#quick-start-docker)
3. [Manual Setup](#manual-setup)
4. [Dataset Setup](#dataset-setup)
5. [Module Breakdown](#module-breakdown)
6. [Model Design & Rationale](#model-design--rationale)
7. [Evaluation Metrics](#evaluation-metrics)
8. [Prompt Engineering & Hallucination Control](#prompt-engineering--hallucination-control)
9. [Known Limitations](#known-limitations)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Browser (Single-Page App)                    │
│  EDA Tab │ Insights Tab │ Risk Score │ Explainability │ Chat    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP / REST
┌──────────────────────────▼──────────────────────────────────────┐
│                      Flask Application (app.py)                 │
│                                                                 │
│  /api/eda/*      /api/predict    /api/metrics   /api/chat       │
└───┬──────────────────┬───────────────┬──────────────┬──────────┘
    │                  │               │              │
    ▼                  ▼               ▼              ▼
SQLite DB         ML Pipeline     SHAP Engine    NL→SQL Agent
(applications)  (LightGBM)     (TreeExplainer)  (LLM + SQLite)
    ▲                  ▲
    │                  │
    └──── Data Pipeline (loader.py → preprocessor.py) ────────────
                          ▲
                   Home Credit CSVs (data/)
```

### Component Map

| Layer | File(s) | Purpose |
|---|---|---|
| Data Loading | `src/data/loader.py` | Load & join all CSV tables |
| Preprocessing | `src/data/preprocessor.py` | Clean, engineer, encode, impute |
| Training | `src/ml/train.py` | LightGBM + 5-fold CV + SHAP |
| Inference | `src/ml/predict.py` | Single/batch scoring + local SHAP |
| Evaluation | `src/ml/evaluate.py` | Metrics, ROC/PR curves |
| Talk-to-Data | `src/talk_to_data/nl_to_sql.py` | NL → SQL via LLM |
| Query Runner | `src/talk_to_data/query_runner.py` | Execute SQL on SQLite |
| Prompt Templates | `src/talk_to_data/prompt_templates.py` | Versioned prompts |
| DB Builder | `scripts/build_db.py` | CSV → SQLite |
| Flask API | `app.py` | REST API |
| Frontend | `ui/` | Single-page dark UI |

---

## Quick Start (Docker)

### Prerequisites
- Docker & Docker Compose installed
- Home Credit dataset downloaded from Kaggle (see [Dataset Setup](#dataset-setup))
- An Anthropic API key (or OpenAI key — configurable)

### Steps

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd credit_risk_platform

# 2. Place dataset files in ./data/
#    Required: application_train.csv
#    Optional: bureau.csv, previous_application.csv (adds more features)

# 3. Set up environment variables
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY (or OPENAI_API_KEY)
nano .env

# 4. Run with Docker Compose
docker-compose up --build

# 5. Open browser
open http://localhost:5000
```

The container will automatically:
1. Build the SQLite database from the CSV files
2. Train the LightGBM model (takes ~5-15 min on full data)
3. Backfill risk scores into the database
4. Start the Flask server

> **Tip**: Set `DATA_SAMPLE=50000` in `.env` for a fast demo run (~2 min training).

---

## Manual Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env — add ANTHROPIC_API_KEY

# Build SQLite database
python scripts/build_db.py --sample 50000   # or omit --sample for full data

# Train model
python -c "from src.ml.train import train; train()"

# Backfill risk scores
python scripts/update_risk_scores.py

# Run the app
python app.py
```

Visit **http://localhost:5000**

---

## Dataset Setup

Download from: https://www.kaggle.com/competitions/home-credit-default-risk/data

Place these files in `./data/`:

| File | Required | Notes |
|---|---|---|
| `application_train.csv` | ✅ Yes | Main training data |
| `bureau.csv` | Recommended | Adds bureau loan features |
| `previous_application.csv` | Recommended | Adds prior app features |
| Other CSVs | Optional | Not used in current pipeline |

---

## Module Breakdown

### Module 1 — Exploratory Data Analysis
- **File**: `notebooks/eda.py`
- Covers: class imbalance, demographics, financial distributions, missing data, default drivers
- Run standalone: `python notebooks/eda.py` → saves charts to `notebooks/eda_output/`
- Key insights:
  1. ~8-9% default rate → significant class imbalance
  2. Younger applicants (< 30) default at 2× average rate
  3. EXT_SOURCE_2 strongly inversely correlated with default
  4. Loans > 3× annual income show significantly higher default risk
  5. Missing EXT_SOURCE data is itself a risk signal

### Module 2 — Talk-to-Data System
- **Files**: `src/talk_to_data/`
- Architecture: User question → LLM (NL→SQL) → SQLite → LLM (interpret results) → UI
- Prompt versioning in `prompt_templates.py` (v1 fallback, v2 production)
- Two-layer SQL guard: regex + LLM safety check
- Sample working queries built into the UI chips

### Module 3 — Machine Learning Layer
- **Files**: `src/ml/train.py`, `predict.py`, `evaluate.py`
- Algorithm: **LightGBM** (gradient boosted trees)
- Class imbalance: `class_weight='balanced'` + threshold tuning
- Risk bands: Low (< 30), Medium (30-60), High (> 60) probability score
- Output per prediction: probability, risk score (0-100), risk band, SHAP top-10

### Module 4 — Explainable AI
- **SHAP TreeExplainer** — exact, fast for tree models
- Global: mean |SHAP| importance across 2000-row sample
- Local: per-prediction contribution waterfall (shown in UI)
- Business language: "increases risk" / "decreases risk" direction labels

### Module 5 — User Interface
- Single-page dark-themed dashboard (`ui/`)
- 5 sections: EDA, Key Insights, Risk Score, Explainability, Ask the Data
- Charts: Chart.js with ChartDataLabels plugin
- Fully responsive, no framework dependencies

### Module 6 — Dockerized Deployment
- `Dockerfile` — Python 3.11-slim base
- `docker-compose.yml` — single service with volume mounts
- `docker-entrypoint.sh` — automated setup on first run
- `docker-compose up --build` → full stack in one command

---

## Model Design & Rationale

### Why LightGBM?
- Best-in-class performance on tabular, imbalanced financial data
- Native categorical handling and fast training
- SHAP TreeExplainer supports exact (not approximate) values
- Industry standard for credit scoring

### Class Imbalance Strategy
| Technique | Implementation |
|---|---|
| `class_weight='balanced'` | Automatically scales positive class weight |
| Threshold optimisation | OOF F1-maximising threshold (not fixed 0.5) |
| Stratified K-Fold | Preserves class ratio in every fold |
| PR-AUC monitoring | More informative than ROC-AUC for imbalanced data |

### Feature Engineering
- **CREDIT_TO_INCOME**: loan / income — top SHAP feature
- **ANNUITY_TO_INCOME**: monthly burden / income
- **EXT_SOURCE_MEAN/MIN**: aggregate of bureau scores
- **AGE_YEARS / YEARS_EMPLOYED**: from negative day counts
- Bureau and previous application aggregates (when available)

---

## Evaluation Metrics

| Metric | Value (5-fold OOF) |
|---|---|
| ROC-AUC | ~0.76 |
| PR-AUC | ~0.29 |
| Best F1 | ~0.35 |
| Optimised threshold | ~0.35 |

*Exact numbers appear in the Model Metrics tab after training.*

---

## Prompt Engineering & Hallucination Control

### NL→SQL Prompt Design
- **Schema grounding**: Full table schema injected in system prompt
- **Strict output format**: "Return ONLY a valid SQLite SQL query" — prevents prose leakage
- **Business aliases**: Domain-specific column explanations (e.g., `DAYS_BIRTH` = "negative days")
- **Computed column hints**: Age calculation formula provided to prevent errors
- **Row limits**: Hard-coded `LIMIT 500` prevents runaway queries

### Hallucination Control
1. **Two-layer SQL guard**: Regex check (instant) + LLM safety check (secondary)
2. **DML blocking**: Any INSERT/UPDATE/DELETE is rejected before execution
3. **Error boundaries**: All SQL errors returned as structured JSON, never exposed raw
4. **Interpretation prompt**: LLM interprets *actual query results* — no fabrication possible
5. **Prompt version control**: v1 fallback if v2 fails; templates in one file for auditability
6. **Token budget**: `max_tokens=400` for SQL (prevents bloat), `max_tokens=300` for interpretation

---

## Known Limitations & Improvements

| Limitation | Suggested Improvement |
|---|---|
| Single-node SQLite | Migrate to PostgreSQL for concurrent users |
| No auth layer | Add JWT authentication for multi-user deployment |
| Model retraining is manual | Add a `/api/retrain` endpoint with progress streaming |
| Chat has no session memory | Add multi-turn conversation context |
| SHAP computed at inference | Pre-compute global SHAP once; cache in Redis |
| No model versioning | Integrate MLflow for experiment tracking |
| EDA charts are static (SQL) | Add interactive Plotly charts |
