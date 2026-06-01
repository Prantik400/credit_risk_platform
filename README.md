# NeoStats – AI-Powered Credit Risk Intelligence Platform

> Candidate Assignment — AI Engineer Role

A full-stack credit risk platform that combines:

* Exploratory Data Analysis (EDA)
* Machine Learning-Based Risk Prediction
* Explainable AI (SHAP)
* Conversational Data Interface (NL → SQL)
* Dockerized Deployment

---

# Table of Contents

1. Architecture Overview
2. Quick Start (Docker)
3. Manual Setup
4. Dataset Setup
5. Module Breakdown
6. Model Design & Rationale
7. Evaluation Metrics
8. Prompt Engineering & Hallucination Control
9. Known Limitations & Future Improvements

---

# Architecture Overview

```text
┌─────────────────────────────────────────────────────────────────┐
│                    Browser (Single-Page App)                    │
│   EDA Tab │ Insights Tab │ Risk Score │ Explainability │ Chat   │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP / REST
┌──────────────────────────▼──────────────────────────────────────┐
│                    Flask Application (app.py)                   │
│                                                                 │
│  /api/eda/*  /api/predict  /api/metrics  /api/chat              │
└───┬──────────────────┬───────────────┬──────────────┬───────────┘
    │                  │               │              │
    ▼                  ▼               ▼              ▼
SQLite DB         ML Pipeline      SHAP Engine    NL→SQL Agent
(applications)    (LightGBM)    (TreeExplainer)  (LLM + SQLite)
    ▲                  ▲
    │                  │
    └──── Data Pipeline (loader.py → preprocessor.py) ────────────
                          ▲
                     Home Credit CSVs
```

## Component Map

| Layer            | File(s)                                | Purpose                                             |
| ---------------- | -------------------------------------- | --------------------------------------------------- |
| Data Loading     | `src/data/loader.py`                   | Load and merge CSV datasets                         |
| Preprocessing    | `src/data/preprocessor.py`             | Cleaning, feature engineering, encoding, imputation |
| Training         | `src/ml/train.py`                      | LightGBM training with CV and SHAP                  |
| Inference        | `src/ml/predict.py`                    | Single and batch prediction                         |
| Evaluation       | `src/ml/evaluate.py`                   | ROC, PR curves, F1 optimization                     |
| NL → SQL         | `src/talk_to_data/nl_to_sql.py`        | Natural language query generation                   |
| Query Runner     | `src/talk_to_data/query_runner.py`     | Safe SQL execution                                  |
| Prompt Templates | `src/talk_to_data/prompt_templates.py` | Prompt engineering and safety                       |
| DB Builder       | `scripts/build_db.py`                  | SQLite database creation                            |
| Backend API      | `app.py`                               | Flask REST API                                      |
| Frontend         | `ui/`                                  | Dashboard interface                                 |

---

# Quick Start (Docker)

## Prerequisites

* Docker
* Docker Compose
* Home Credit Dataset
* OpenRouter API Key

## Steps

```bash
# Clone repository
git clone <your-repo-url>
cd credit_risk_platform

# Place dataset files inside ./data/

# Create environment file
cp .env.example .env

# Add your API key
nano .env

# Start application
docker-compose up --build

# Open application
http://localhost:5000
```

### What Happens Automatically?

* Builds SQLite database
* Trains LightGBM model
* Generates risk scores
* Starts Flask API server

### Fast Demo Mode

```env
DATA_SAMPLE=50000
```

Processes a smaller dataset for quick testing.

---

# Manual Setup

```bash
# Create virtual environment
python -m venv venv

# Activate
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env

# Build database
python scripts/build_db.py --sample 50000

# Train model
python -c "from src.ml.train import train; train()"

# Update risk scores
python scripts/update_risk_scores.py

# Start server
python app.py
```

Application URL:

```text
http://localhost:5000
```

---

# Dataset Setup

Dataset Source:

Home Credit Default Risk Competition

Required files:

| File                     | Required    | Description                  |
| ------------------------ | ----------- | ---------------------------- |
| application_train.csv    | Yes         | Main training dataset        |
| bureau.csv               | Recommended | External credit history      |
| previous_application.csv | Recommended | Historical loan applications |
| Other CSVs               | Optional    | Additional tables            |

Place all files inside:

```text
data/
```

---

# Module Breakdown

## Module 1 – Exploratory Data Analysis

**Location**

```text
notebooks/eda.py
```

### Analysis Performed

* Class imbalance detection
* Demographic profiling
* Financial exposure analysis
* Missing value assessment
* Default correlation discovery

### Key Findings

* Default rate around 8–9%
* Younger applicants show higher default rates
* `EXT_SOURCE_2` strongly predicts repayment behavior
* High loan-to-income ratios increase risk
* Missing values contain useful signals

---

## Module 2 – Talk-to-Data System

**Location**

```text
src/talk_to_data/
```

Pipeline:

```text
User Query
   ↓
NL → SQL
   ↓
Safe SQLite Execution
   ↓
Result Enrichment
   ↓
Natural Language Response
```

Features:

* Interactive prompt chips
* Safe query execution
* Conversational analytics

---

## Module 3 – Machine Learning Layer

**Files**

```text
src/ml/train.py
src/ml/predict.py
src/ml/evaluate.py
```

### Model

* LightGBM

### Class Imbalance Handling

```python
class_weight='balanced'
```

### Risk Categories

| Probability | Risk Level |
| ----------- | ---------- |
| < 30%       | Low        |
| 30–60%      | Medium     |
| > 60%       | High       |

Prediction output includes:

* Probability
* Risk score (0–100)
* Risk category
* Top SHAP features

---

## Module 4 – Explainable AI (XAI)

### Engine

SHAP TreeExplainer

### Features

#### Global Explanations

* Mean SHAP importance
* Feature ranking

#### Local Explanations

* Individual prediction breakdown
* Waterfall visualizations
* Risk increase/decrease explanations

---

## Module 5 – User Interface

### Dashboard Sections

1. EDA
2. Insights
3. Risk Scoring
4. Explainability
5. Ask the Data

### Technology

* Vanilla JavaScript
* Chart.js
* ChartDataLabels

No React or Vue dependency.

---

## Module 6 – Dockerized Deployment

### Base Image

```dockerfile
python:3.11-slim
```

### Orchestration

```text
docker-compose.yml
```

### Startup Logic

```text
docker-entrypoint.sh
```

Responsible for:

* Database creation
* Model training
* Service initialization

---

# Model Design & Rationale

## Why LightGBM?

* Fast training on tabular data
* Handles non-linear relationships
* Supports missing values efficiently
* SHAP-compatible

## Why OpenRouter + Llama?

### Benefits

* Free-tier access
* Unified API
* Easy model switching
* Lightweight inference

### Current Model

```text
liquid/lfm-2.5-1.2b-instruct
```

---

# Class Imbalance Strategy

| Strategy                | Implementation            |
| ----------------------- | ------------------------- |
| Cost-Sensitive Learning | `class_weight='balanced'` |
| Threshold Optimization  | F1-based tuning           |
| Stratified Validation   | Stratified K-Fold         |
| Metric Selection        | PR-AUC focus              |

---

# Feature Engineering Highlights

### CREDIT_TO_INCOME

Loan amount relative to annual income.

### ANNUITY_TO_INCOME

Monthly payment burden.

### EXT_SOURCE_MEAN / MIN

Aggregated external credit indicators.

### AGE_YEARS

Derived from `DAYS_BIRTH`.

### YEARS_EMPLOYED

Derived from employment duration.

---

# Evaluation Metrics

| Metric            | Value  |
| ----------------- | ------ |
| ROC-AUC           | 0.7447 |
| PR-AUC            | 0.2344 |
| Best F1 Score     | 0.3054 |
| Optimal Threshold | 0.6100 |

Metrics are displayed dynamically in the dashboard after training.

---

# Prompt Engineering & Hallucination Control

## NL → SQL Prompt Design

### Schema Grounding

Database schema injected into prompts.

### Strict Output Enforcement

```text
Return ONLY a valid SQLite SQL query.
```

### Domain Mapping

Business terminology mapped to database fields.

### Deterministic Computation Rules

Predefined formulas supplied to the model.

### Query Limits

```sql
LIMIT 500
```

Prevents excessive scans.

---

# Hallucination Control Pipeline

```text
User Query
    ↓
LLM SQL Generation
    ↓
Regex Validation
    ↓
Safety Audit
    ↓
SQLite Execution
    ↓
Result Interpretation
```

## Safety Measures

* Regex validation
* DML command blocking
* SQL exception handling
* Grounded response generation
* Token limits

Blocked commands:

```sql
INSERT
UPDATE
DELETE
DROP
```

---

# Known Limitations & Future Improvements

| Limitation             | Proposed Improvement              |
| ---------------------- | --------------------------------- |
| SQLite concurrency     | PostgreSQL migration              |
| No authentication      | JWT / OAuth2                      |
| Manual retraining      | Celery-based retraining API       |
| Stateless chat         | Redis session memory              |
| SHAP latency           | Precomputed explanations          |
| No experiment tracking | MLflow / Weights & Biases         |
| Static charts          | Plotly interactive visualizations |

---

# Future Roadmap

* PostgreSQL backend support
* Secure authentication layer
* Real-time model retraining
* Conversational memory
* Faster explainability
* Experiment tracking
* Interactive analytics dashboard
