import os
import re
import urllib.request
import json
from src.utils.logger import get_logger
from src.talk_to_data.prompt_templates import (
    SYSTEM_PROMPT, USER_PROMPT,
    SQL_GUARD_SYSTEM, SQL_GUARD_USER,
    INTERPRET_SYSTEM, INTERPRET_USER,
)

logger = get_logger(__name__)

def _get_model(): return os.environ.get("LLM_MODEL", "meta-llama/llama-3-8b-instruct:free")
def _get_key():   return os.environ.get("GROQ_API_KEY", "")

def _call_llm(system, user, max_tokens=512):
    payload = json.dumps({
        "model": _get_model(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.1,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_get_key()}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"].strip()

def _clean_sql(raw):
    raw = raw.strip()
    raw = re.sub(r"```(?:sql)?", "", raw, flags=re.IGNORECASE).replace("```", "")
    return raw.strip()

def _guard_sql(sql):
    dangerous = re.compile(
        r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|EXEC|EXECUTE)\b",
        re.IGNORECASE
    )
    return not bool(dangerous.search(sql))

def question_to_sql(question):
    logger.info(f"NL->SQL for: {question!r}")
    sql = _clean_sql(_call_llm(SYSTEM_PROMPT, USER_PROMPT.format(question=question), max_tokens=400))
    if not _guard_sql(sql):
        raise ValueError(f"Unsafe SQL blocked: {sql}")
    return sql

def interpret_results(question, sql, results_json):
    try:
        return _call_llm(INTERPRET_SYSTEM, INTERPRET_USER.format(
            question=question, sql=sql, results_json=results_json), max_tokens=300)
    except Exception as e:
        logger.warning(f"Interpretation failed: {e}")
        return "Query executed successfully. Please review the results table below."
