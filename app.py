import os
import json
import traceback
import sqlite3
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_from_directory
try:
    from flask_cors import CORS
    _cors_available = True
except ImportError:
    _cors_available = False

from src.utils.config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG, MODELS_DIR, DB_PATH
from src.utils.helpers import model_is_trained
from src.utils.logger import get_logger

logger = get_logger("app")

app = Flask(__name__, template_folder="ui/templates", static_folder="ui/static")
if _cors_available:
    CORS(app)


def _model_ready():
    return model_is_trained(MODELS_DIR)


def _db_ready():
    return os.path.exists(DB_PATH)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def status():
    return jsonify({
        "model_ready": _model_ready(),
        "db_ready":    _db_ready(),
        "version":     "1.0.0",
    })


@app.route("/api/eda/summary")
def eda_summary():
    
    if not _db_ready():
        return jsonify({"error": "Database not ready"}), 503
    try:
        conn = sqlite3.connect(DB_PATH)
        
        total     = pd.read_sql("SELECT COUNT(*) AS n FROM applications", conn).iloc[0, 0]
        defaults  = pd.read_sql("SELECT SUM(TARGET) AS n FROM applications", conn).iloc[0, 0]
        avg_income= pd.read_sql("SELECT AVG(AMT_INCOME_TOTAL) AS v FROM applications", conn).iloc[0, 0]
        avg_credit= pd.read_sql("SELECT AVG(AMT_CREDIT) AS v FROM applications", conn).iloc[0, 0]
        avg_age   = pd.read_sql("SELECT AVG(-DAYS_BIRTH/365.0) AS v FROM applications", conn).iloc[0, 0]

        gender_dist = pd.read_sql(
            "SELECT CODE_GENDER, COUNT(*) AS count FROM applications GROUP BY CODE_GENDER", conn
        ).to_dict(orient="records")

        contract_dist = pd.read_sql(
            "SELECT NAME_CONTRACT_TYPE, COUNT(*) AS count, AVG(TARGET)*100 AS default_rate "
            "FROM applications GROUP BY NAME_CONTRACT_TYPE", conn
        ).to_dict(orient="records")

        income_type = pd.read_sql(
            "SELECT NAME_INCOME_TYPE, COUNT(*) AS count, ROUND(AVG(TARGET)*100,2) AS default_rate "
            "FROM applications GROUP BY NAME_INCOME_TYPE ORDER BY count DESC LIMIT 10", conn
        ).to_dict(orient="records")

        education = pd.read_sql(
            "SELECT NAME_EDUCATION_TYPE, COUNT(*) AS count, ROUND(AVG(TARGET)*100,2) AS default_rate "
            "FROM applications GROUP BY NAME_EDUCATION_TYPE ORDER BY count DESC", conn
        ).to_dict(orient="records")

        risk_band_dist = pd.read_sql(
            "SELECT RISK_BAND, COUNT(*) AS count FROM applications "
            "WHERE RISK_BAND IS NOT NULL GROUP BY RISK_BAND", conn
        ).to_dict(orient="records")

        conn.close()
        return jsonify({
            "total_applicants": int(total),
            "total_defaults":   int(defaults),
            "default_rate":     round(float(defaults) / float(total) * 100, 2),
            "avg_income":       round(float(avg_income), 2),
            "avg_credit":       round(float(avg_credit), 2),
            "avg_age":          round(float(avg_age), 1),
            "gender_dist":      gender_dist,
            "contract_dist":    contract_dist,
            "income_type":      income_type,
            "education":        education,
            "risk_band_dist":   risk_band_dist,
        })
    except Exception as e:
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route("/api/eda/insights")
def eda_insights():
    
    if not _db_ready():
        return jsonify({"error": "Database not ready"}), 503
    try:
        conn = sqlite3.connect(DB_PATH)

        # Default rate by age group
        age_default = pd.read_sql("""
            SELECT 
                CASE 
                    WHEN -DAYS_BIRTH/365 < 30 THEN 'Under 30'
                    WHEN -DAYS_BIRTH/365 < 40 THEN '30-40'
                    WHEN -DAYS_BIRTH/365 < 50 THEN '40-50'
                    WHEN -DAYS_BIRTH/365 < 60 THEN '50-60'
                    ELSE 'Over 60'
                END AS age_group,
                COUNT(*) AS count,
                ROUND(AVG(TARGET)*100, 2) AS default_rate
            FROM applications
            GROUP BY age_group ORDER BY default_rate DESC
        """, conn).to_dict(orient="records")

        # External score vs default
        ext_bins = pd.read_sql("""
            SELECT 
                ROUND(EXT_SOURCE_2, 1) AS ext_score_bin,
                ROUND(AVG(TARGET)*100, 2) AS default_rate,
                COUNT(*) AS count
            FROM applications
            WHERE EXT_SOURCE_2 IS NOT NULL
            GROUP BY ext_score_bin
            ORDER BY ext_score_bin
        """, conn).to_dict(orient="records")

        #  Credit-to-income vs default
        credit_income = pd.read_sql("""
            SELECT 
                CASE 
                    WHEN AMT_CREDIT/AMT_INCOME_TOTAL < 1 THEN '< 1x'
                    WHEN AMT_CREDIT/AMT_INCOME_TOTAL < 2 THEN '1-2x'
                    WHEN AMT_CREDIT/AMT_INCOME_TOTAL < 3 THEN '2-3x'
                    WHEN AMT_CREDIT/AMT_INCOME_TOTAL < 5 THEN '3-5x'
                    ELSE '> 5x'
                END AS credit_income_ratio,
                COUNT(*) AS count,
                ROUND(AVG(TARGET)*100, 2) AS default_rate
            FROM applications
            WHERE AMT_INCOME_TOTAL > 0
            GROUP BY credit_income_ratio
        """, conn).to_dict(orient="records")

        # Occupations with highest default
        occupation = pd.read_sql("""
            SELECT OCCUPATION_TYPE, COUNT(*) AS count, 
                   ROUND(AVG(TARGET)*100,2) AS default_rate
            FROM applications WHERE OCCUPATION_TYPE IS NOT NULL
            GROUP BY OCCUPATION_TYPE ORDER BY default_rate DESC LIMIT 10
        """, conn).to_dict(orient="records")

        #  Missing EXT_SOURCE correlation
        ext_missing = pd.read_sql("""
            SELECT 
                CASE WHEN EXT_SOURCE_1 IS NULL THEN 'Missing' ELSE 'Present' END AS ext1_status,
                ROUND(AVG(TARGET)*100,2) AS default_rate,
                COUNT(*) AS count
            FROM applications GROUP BY ext1_status
        """, conn).to_dict(orient="records")

        conn.close()
        return jsonify({
            "age_default":    age_default,
            "ext_score_bins": ext_bins,
            "credit_income":  credit_income,
            "occupation":     occupation,
            "ext_missing":    ext_missing,
        })
    except Exception as e:
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500



@app.route("/api/predict", methods=["POST"])
def predict():
   
    if not _model_ready():
        return jsonify({"error": "Model not trained yet. Run train.py first."}), 503
    try:
        from src.ml.predict import predict_single
        data = request.get_json(force=True)
        result = predict_single(data)
        return jsonify(result)
    except Exception as e:
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route("/api/metrics")
def metrics():
    
    if not _model_ready():
        return jsonify({"error": "Model not trained"}), 503
    try:
        from src.ml.evaluate import load_saved_metrics
        return jsonify(load_saved_metrics())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/shap-importance")
def shap_importance():
    
    path = os.path.join(MODELS_DIR, "shap_importance.csv")
    if not os.path.exists(path):
        return jsonify({"error": "SHAP data not available"}), 404
    df = pd.read_csv(path).head(20)
    return jsonify(df.to_dict(orient="records"))



@app.route("/api/chat", methods=["POST"])
def chat():
  
    if not _db_ready():
        return jsonify({"error": "Database not ready"}), 503
    try:
        body = request.get_json(force=True)
        question = body.get("question", "").strip()
        if not question:
            return jsonify({"error": "No question provided"}), 400

        from src.talk_to_data.nl_to_sql import question_to_sql, interpret_results
        from src.talk_to_data.query_runner import run_and_describe

        sql = question_to_sql(question)
        result = run_and_describe(sql)

        if not result["success"]:
            return jsonify({
                "success": False,
                "sql":     sql,
                "error":   result["error"],
            })

        insight = interpret_results(question, sql, result["data_json"])

        return jsonify({
            "success":   True,
            "question":  question,
            "sql":       sql,
            "insight":   insight,
            "row_count": result["row_count"],
            "columns":   result["columns"],
            "data":      result["data"][:100],  # cap payload
        })
    except ValueError as e:
        return jsonify({"success": False, "error": str(e), "sql": ""}), 400
    except Exception as e:
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/rules")
def get_rules():
 
    try:
        from src.ml.rules import load_rules
        return jsonify(load_rules())
    except Exception as e:
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route("/api/rules/evaluate", methods=["POST"])
def evaluate_rules():
    
    try:
        from src.ml.rules import apply_rules
        data = request.get_json(force=True)
        result = apply_rules(data)
        return jsonify(result)
    except Exception as e:
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route("/api/rules/generate", methods=["POST"])
def generate_rules():
  
    if not _model_ready():
        return jsonify({"error": "Model not trained yet"}), 503
    try:
        from src.ml.rules import generate_and_save_rules
        result = generate_and_save_rules(sample_size=10_000)
        return jsonify({"success": True, "rule_count": len(result["scorecard_rules"])})
    except Exception as e:
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500



if __name__ == "__main__":
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
