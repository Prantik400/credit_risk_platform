import os
import re
from src.utils.logger import get_logger
from src.talk_to_data.prompt_templates import (
    NL_TO_SQL_SYSTEM_V2, NL_TO_SQL_USER_V2,
    SQL_GUARD_SYSTEM, SQL_GUARD_USER,
    INTERPRET_SYSTEM, INTERPRET_USER,
)

logger = get_logger(__name__)

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "gemini").lower()
LLM_MODEL    = os.environ.get("LLM_MODEL", "gemini-1.5-flash")
GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY", "")
GROQ_API_KEY      = os.environ.get("GROQ_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY    = os.environ.get("OPENAI_API_KEY", "")


def _call_gemini(system: str, user: str, max_tokens: int = 512) -> str:
    import urllib.request, json
    model = LLM_MODEL or "gemini-1.5-flash"
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={GEMINI_API_KEY}"
    )
    # Gemini + user 
    combined = f"{system}\n\n{user}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": combined}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.1},
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def _call_groq(system: str, user: str, max_tokens: int = 512) -> str:
    import urllib.request, json
    model = LLM_MODEL or "llama3-8b-8192"
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.1,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


def _call_anthropic(system: str, user: str, max_tokens: int = 512) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=LLM_MODEL or "claude-3-5-haiku-20241022",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text.strip()


def _call_openai(system: str, user: str, max_tokens: int = 512) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=LLM_MODEL or "gpt-4o-mini",
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    )
    return resp.choices[0].message.content.strip()


def _llm_call(system: str, user: str, max_tokens: int = 512) -> str:
    if LLM_PROVIDER == "gemini":
        return _call_gemini(system, user, max_tokens)
    elif LLM_PROVIDER == "groq":
        return _call_groq(system, user, max_tokens)
    elif LLM_PROVIDER == "anthropic":
        return _call_anthropic(system, user, max_tokens)
    elif LLM_PROVIDER == "openai":
        return _call_openai(system, user, max_tokens)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER}. Choose: gemini, groq, anthropic, openai")


def _clean_sql(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"```(?:sql)?", "", raw, flags=re.IGNORECASE).replace("```", "")
    return raw.strip()


def _guard_sql(sql: str) -> bool:
    """Return True if the SQL is safe (SELECT only)."""
    # Fast rule-based check
    dangerous = re.compile(
        r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|EXEC|EXECUTE)\b",
        re.IGNORECASE
    )
    if dangerous.search(sql):
        return False
    # Optionally ask the LLM as second layer
    try:
        verdict = _llm_call(
            SQL_GUARD_SYSTEM,
            SQL_GUARD_USER.format(sql=sql),
            max_tokens=5,
        ).upper()
        return verdict.startswith("SAFE")
    except Exception:
        # If LLM guard fails rely on regex result
        return True


def question_to_sql(question: str) -> str:
    logger.info(f"NL→SQL for: {question!r}")
    user_prompt = NL_TO_SQL_USER_V2.format(question=question)
    raw = _llm_call(NL_TO_SQL_SYSTEM_V2, user_prompt, max_tokens=400)
    sql = _clean_sql(raw)
    logger.debug(f"Generated SQL: {sql}")

    if not _guard_sql(sql):
        raise ValueError(f"Unsafe SQL blocked: {sql}")

    return sql


def interpret_results(question: str, sql: str, results_json: str) -> str:
    try:
        user_prompt = INTERPRET_USER.format(
            question=question,
            sql=sql,
            results_json=results_json,
        )
        return _llm_call(INTERPRET_SYSTEM, user_prompt, max_tokens=300)
    except Exception as e:
        logger.warning(f"Interpretation failed: {e}")
        return "Query executed successfully. Please review the results table below."
