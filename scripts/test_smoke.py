import os
import sys
import json
import sqlite3
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
errors = []


def check(name, fn):
    try:
        fn()
        print(f"  {PASS} {name}")
    except Exception as e:
        print(f"  {FAIL} {name}: {e}")
        errors.append(name)



print("Running NeoStats Smoke Tests...")

# Importing
print("[ Imports ]")
check("src.utils.config", lambda: __import__("src.utils.config"))
check("src.utils.logger", lambda: __import__("src.utils.logger"))
check("src.utils.helpers", lambda: __import__("src.utils.helpers"))
check("src.utils.docker_utils", lambda: __import__("src.utils.docker_utils"))
check("src.data.preprocessor", lambda: __import__("src.data.preprocessor"))
check("src.ml.rules (scorecard)", lambda: (
    __import__("src.ml.rules", fromlist=["SCORECARD_RULES"]),
))
check("src.talk_to_data.prompt_templates", lambda: __import__("src.talk_to_data.prompt_templates"))
check("src.talk_to_data.query_runner", lambda: __import__("src.talk_to_data.query_runner"))

# Preprocessing
print("\n[ Preprocessor ]")

def _make_synthetic():
    np.random.seed(42)
    n = 100
    return pd.DataFrame({
        "TARGET": np.random.randint(0, 2, n),
        "AMT_INCOME_TOTAL": np.random.uniform(50000, 500000, n),
        "AMT_CREDIT":       np.random.uniform(100000, 1000000, n),
        "AMT_ANNUITY":      np.random.uniform(5000, 50000, n),
        "AMT_GOODS_PRICE":  np.random.uniform(80000, 900000, n),
        "DAYS_BIRTH":       np.random.randint(-25000, -10000, n),
        "DAYS_EMPLOYED":    np.random.randint(-5000, -100, n),
        "DAYS_REGISTRATION":np.random.uniform(-10000, -100, n),
        "DAYS_ID_PUBLISH":  np.random.randint(-5000, -100, n),
        "EXT_SOURCE_1":     np.random.uniform(0, 1, n),
        "EXT_SOURCE_2":     np.random.uniform(0, 1, n),
        "EXT_SOURCE_3":     np.random.uniform(0, 1, n),
        "REGION_POPULATION_RELATIVE": np.random.uniform(0.001, 0.07, n),
        "CNT_FAM_MEMBERS":  np.random.randint(1, 6, n),
        "NAME_CONTRACT_TYPE": np.random.choice(["Cash loans","Revolving loans"], n),
        "CODE_GENDER":      np.random.choice(["M","F"], n),
        "FLAG_OWN_CAR":     np.random.choice(["Y","N"], n),
        "FLAG_OWN_REALTY":  np.random.choice(["Y","N"], n),
        "NAME_INCOME_TYPE": np.random.choice(["Working","Pensioner","Commercial associate"], n),
        "NAME_EDUCATION_TYPE": np.random.choice(["Secondary / secondary special","Higher education"], n),
        "NAME_FAMILY_STATUS": np.random.choice(["Married","Single / not married"], n),
        "NAME_HOUSING_TYPE": np.random.choice(["House / apartment","Rented apartment"], n),
        "OCCUPATION_TYPE":  np.random.choice(["Laborers","Core staff","Managers", None], n),
    })

df = _make_synthetic()

def _test_preprocessor():
    from src.data.preprocessor import CreditPreprocessor
    prep = CreditPreprocessor()
    X = prep.fit_transform(df)
    assert X.shape[0] == 100, "Row count mismatch"
    assert X.isnull().sum().sum() == 0, "Found unhandled NaNs after transformation"

check("fit_transform (no NaNs)", _test_preprocessor)

def _test_transform_single():
    from src.data.preprocessor import CreditPreprocessor
    prep = CreditPreprocessor()
    prep.fit(df)
    row = df.iloc[[0]].copy()
    X = prep.transform(row)
    assert X.shape[0] == 1

check("transform single row", _test_transform_single)

# Engine rules
print("\n[ Rule Engine ]")

def _test_rule_engine():
    from src.ml.rules import apply_rules
    applicant = {
        "AMT_INCOME_TOTAL": 100000,
        "AMT_CREDIT":       600000,
        "AMT_ANNUITY":      50000,
        "DAYS_BIRTH":       -10000,     # ~27 yrs
        "DAYS_EMPLOYED":    -300,       # < 1 yr
        "EXT_SOURCE_1":     0.2,
        "EXT_SOURCE_2":     0.25,       # triggers R01
        "EXT_SOURCE_3":     0.2,        # mean < 0.30 triggers R06
    }
    result = apply_rules(applicant)
    assert "triggered_rules" in result
    assert result["triggered_count"] > 0, "Should trigger at least 1 rule"

check("rule engine triggers correctly", _test_rule_engine)

def _test_rule_clean():
    from src.ml.rules import apply_rules
    clean = {
        "AMT_INCOME_TOTAL": 500000,
        "AMT_CREDIT":       400000,
        "AMT_ANNUITY":      20000,
        "DAYS_BIRTH":       -18000,
        "DAYS_EMPLOYED":    -3000,
        "EXT_SOURCE_1":     0.8,
        "EXT_SOURCE_2":     0.75,
        "EXT_SOURCE_3":     0.7,
    }
    result = apply_rules(clean)
    assert result["triggered_count"] == 0, "Clean applicant should trigger 0 rules"

check("rule engine: clean applicant = 0 triggers", _test_rule_clean)

# Prompt Templates 
print("\n[ Prompt Templates ]")

def _test_prompts():
    from src.talk_to_data.prompt_templates import (
        NL_TO_SQL_SYSTEM_V2, NL_TO_SQL_USER_V2, INTERPRET_SYSTEM
    )
    assert "applications" in NL_TO_SQL_SYSTEM_V2
    assert "{question}" in NL_TO_SQL_USER_V2
    assert len(INTERPRET_SYSTEM) > 50

check("prompt templates load & contain expected content", _test_prompts)

# SQLite DB 
print("\n[ SQLite ]")

def _test_sqlite():
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE applications (
        SK_ID_CURR INTEGER, TARGET INTEGER, CODE_GENDER TEXT,
        AMT_INCOME_TOTAL REAL, RISK_BAND TEXT
    )""")
    conn.execute("INSERT INTO applications VALUES (1, 0, 'M', 180000, 'Low')")
    conn.commit()
    row = conn.execute("SELECT COUNT(*) FROM applications").fetchone()
    assert row[0] == 1
    conn.close()

check("SQLite in-memory CRUD", _test_sqlite)

# Flask imports 
print("\n[ Flask App ]")

def _test_flask_import():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "app", os.path.join(os.path.dirname(__file__), "..", "app.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "app"), "Flask app object not found"

check("app.py imports without error", _test_flask_import)

# Summary
print("\n")
if errors:
    print(f"  \033[91m{len(errors)} test(s) FAILED: {', '.join(errors)}\033[0m")
    sys.exit(1)
else:
    print("  \033[92mAll smoke tests passed ✓\033[0m")
print("\n")
