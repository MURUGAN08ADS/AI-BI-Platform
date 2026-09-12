"""Natural language -> SQL -> answer, using the Groq API.

PIPELINE
    question
      -> build prompt (schema + rules + question)
      -> Groq LLM generates SQL
      -> sql_guard.validate_sql()          <-- untrusted input stops here if unsafe
      -> execute on the READ-ONLY connection
      -> Groq LLM turns rows into a business answer
      -> return {answer, sql, rows}

The SQL is always returned to the caller so an analyst can audit exactly
what ran — a black-box answer is not trustworthy in a BI tool.
"""
from __future__ import annotations

import json

import httpx
from sqlalchemy import text

from app.config import settings
from app.chatbot.sql_guard import (UnsafeSQLError, clean_llm_sql, validate_sql)
from app.database.session import readonly_engine

# The model can only write correct SQL if it knows the schema. This is
# kept terse on purpose: a compact, accurate schema beats a long one.
SCHEMA_PROMPT = """
Star-schema warehouse (PostgreSQL).

fact_sales(sales_key, date_key, customer_key, product_key, location_key,
           order_id, quantity, unit_price, discount, revenue, cost, profit)
dim_date(date_key, full_date, year, quarter, month, month_name, day, day_name, is_weekend)
dim_customer(customer_key, customer_id, customer_name, segment)
dim_product(product_key, product_id, product_name, category, sub_category)
dim_location(location_key, city, state, region, country)

Joins:
  fact_sales.date_key     = dim_date.date_key
  fact_sales.customer_key = dim_customer.customer_key
  fact_sales.product_key  = dim_product.product_key
  fact_sales.location_key = dim_location.location_key

Measures live on fact_sales: revenue, profit, quantity.
Descriptive attributes live on the dim_ tables.
""".strip()

SQL_RULES = """
Rules:
1. Return ONE PostgreSQL SELECT statement and nothing else. No prose, no markdown.
2. Never write INSERT, UPDATE, DELETE, DROP, ALTER, CREATE or TRUNCATE.
3. Only use the tables listed in the schema.
4. Always JOIN a dimension when the question refers to its attributes.
5. Aggregate with SUM/COUNT/AVG and GROUP BY where the question implies it.
6. Add ORDER BY and LIMIT for "top"/"best"/"worst" questions (default LIMIT 10).
7. Use ROUND(x::numeric, 2) for money.
8. If the question cannot be answered from this schema, return exactly: NO_QUERY
""".strip()


class ChatbotError(Exception):
    pass


async def _groq(messages: list[dict], temperature: float = 0.0, max_tokens: int = 700) -> str:
    """One call to the Groq chat-completions endpoint."""
    if not settings.GROQ_API_KEY:
        raise ChatbotError("GROQ_API_KEY is not set. Add it to your .env file.")
    payload = {
        "model": settings.GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}",
               "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(settings.GROQ_URL, json=payload, headers=headers)
    if resp.status_code != 200:
        raise ChatbotError(f"Groq API error {resp.status_code}: {resp.text[:200]}")
    return resp.json()["choices"][0]["message"]["content"]


async def generate_sql(question: str) -> str:
    """Ask the model for a query. Temperature 0 — SQL should be deterministic."""
    messages = [
        {"role": "system",
         "content": f"You convert business questions into PostgreSQL queries.\n\n"
                    f"{SCHEMA_PROMPT}\n\n{SQL_RULES}"},
        {"role": "user", "content": question},
    ]
    return clean_llm_sql(await _groq(messages))


def execute_readonly(sql: str) -> tuple[list[str], list[list]]:
    """Run validated SQL on the read-only connection."""
    with readonly_engine.connect() as conn:
        result = conn.execute(text(sql))
        cols = list(result.keys())
        rows = [list(r) for r in result.fetchall()]
    return cols, rows


async def explain_results(question: str, sql: str, cols: list[str], rows: list[list]) -> str:
    """Turn the result set into a short business answer."""
    preview = [dict(zip(cols, r)) for r in rows[:25]]
    messages = [
        {"role": "system",
         "content": "You are a business analyst. Answer the user's question from the query "
                    "results in 2-4 sentences. Quote concrete numbers. Use Indian Rupee (Rs) "
                    "for money. If the result is empty, say no matching data was found. "
                    "Do not invent figures that are not in the results."},
        {"role": "user",
         "content": f"Question: {question}\n\nSQL: {sql}\n\n"
                    f"Results ({len(rows)} rows, showing up to 25):\n"
                    f"{json.dumps(preview, default=str, indent=2)}"},
    ]
    return (await _groq(messages, temperature=0.2, max_tokens=400)).strip()


async def answer_question(question: str) -> dict:
    """Full chatbot flow. Never raises on unsafe SQL — reports it instead."""
    sql = await generate_sql(question)

    if sql.strip().upper() == "NO_QUERY":
        return {"answer": "That question can't be answered from the sales warehouse. "
                          "Try asking about revenue, profit, products, customers, regions or dates.",
                "sql": None, "columns": [], "rows": [], "blocked": False}

    try:
        safe_sql = validate_sql(sql)
    except UnsafeSQLError as exc:
        # The query is discarded, never executed.
        return {"answer": f"That request produced a query I'm not allowed to run ({exc}). "
                          f"The assistant can only read sales data.",
                "sql": sql, "columns": [], "rows": [], "blocked": True}

    try:
        cols, rows = execute_readonly(safe_sql)
    except Exception as exc:  # noqa: BLE001
        return {"answer": f"The query failed to run: {str(exc)[:200]}",
                "sql": safe_sql, "columns": [], "rows": [], "blocked": False}

    answer = await explain_results(question, safe_sql, cols, rows)
    return {"answer": answer, "sql": safe_sql, "columns": cols,
            "rows": rows[:100], "blocked": False}
