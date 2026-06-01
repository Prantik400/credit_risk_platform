"""config.py – Central configuration pulled from environment variables."""
import os

# Directories
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR   = os.environ.get("DATA_DIR",   os.path.join(BASE_DIR, "data"))
MODELS_DIR = os.environ.get("MODELS_DIR", os.path.join(BASE_DIR, "models"))
DB_PATH    = os.environ.get("DB_PATH",    os.path.join(BASE_DIR, "sql", "credit_risk.db"))

# Development: sample rows (None = full dataset)
_sample = os.environ.get("DATA_SAMPLE", "")
DATA_SAMPLE = int(_sample) if _sample.isdigit() else None

# LLM — default is Gemini (free)
LLM_PROVIDER   = os.environ.get("LLM_PROVIDER", "gemini")
LLM_MODEL      = os.environ.get("LLM_MODEL",    "gemini-1.5-flash")
GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY",    "")
GROQ_API_KEY      = os.environ.get("GROQ_API_KEY",      "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY    = os.environ.get("OPENAI_API_KEY",    "")

# Flask
FLASK_HOST  = os.environ.get("FLASK_HOST", "0.0.0.0")
FLASK_PORT  = int(os.environ.get("FLASK_PORT", 5000))
FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
