"""Analytical queries powering the dashboard.

All queries are hand-written SQL (not LLM-generated) because dashboard
numbers must be exact and repeatable. The LLM path is for exploration;
this path is for the numbers the business reports on.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def _rows(db: Session, sql: str, **params) -> list[dict]:
    res = db.execute(text(sql), params)
    cols = list(res.keys())
    return [dict(zip(cols, r)) for r in res.fetchall()]


def _one(db: Session, sql: str, **params) -> dict:
    out = _rows(db, sql, **params)
    return out[0] if out else {}


def kpi_summary(db: Session) -> dict:
    """Headline KPI cards, plus month-over-month growth."""
    totals = _one(db, """
        SELECT COALESCE(SUM(revenue),0)          AS total_revenue,
               COALESCE(SUM(profit),0)           AS total_profit,
               COUNT(DISTINCT order_id)          AS orders,
               COUNT(DISTINCT customer_key)      AS customers,
               COALESCE(SUM(quantity),0)         AS units_sold,
               COALESCE(AVG(revenue),0)          AS avg_order_value
        FROM fact_sales
    """)

    growth = _one(db, """
        WITH monthly AS (
            SELECT d.year, d.month, SUM(f.revenue) AS revenue
            FROM fact_sales f JOIN dim_date d ON f.date_key = d.date_key
            GROUP BY d.year, d.month
            ORDER BY d.year DESC, d.month DESC
            LIMIT 2
        )
        SELECT MAX(revenue) FILTER (WHERE rn = 1) AS current_month,
               MAX(revenue) FILTER (WHERE rn = 2) AS prior_month
        FROM (SELECT revenue, ROW_NUMBER() OVER () AS rn FROM monthly) t
    """)

    cur = float(growth.get("current_month") or 0)
    prev = float(growth.get("prior_month") or 0)
    totals["growth_rate"] = round(((cur - prev) / prev) * 100, 2) if prev else 0.0

    rev = float(totals.get("total_revenue") or 0)
    prof = float(totals.get("total_profit") or 0)
    totals["profit_margin"] = round((prof / rev) * 100, 2) if rev else 0.0
    return {k: (float(v) if isinstance(v, (int, float)) else v) for k, v in totals.items()}


def monthly_sales(db: Session) -> list[dict]:
    return _rows(db, """
        SELECT d.year, d.month, d.month_name,
               ROUND(SUM(f.revenue)::numeric, 2) AS revenue,
               ROUND(SUM(f.profit)::numeric, 2)  AS profit
        FROM fact_sales f JOIN dim_date d ON f.date_key = d.date_key
        GROUP BY d.year, d.month, d.month_name
        ORDER BY d.year, d.month
    """)


def top_products(db: Session, limit: int = 10) -> list[dict]:
    return _rows(db, """
        SELECT p.product_name, p.category,
               ROUND(SUM(f.revenue)::numeric, 2) AS revenue,
               ROUND(SUM(f.profit)::numeric, 2)  AS profit,
               SUM(f.quantity)                   AS units
        FROM fact_sales f JOIN dim_product p ON f.product_key = p.product_key
        GROUP BY p.product_name, p.category
        ORDER BY revenue DESC
        LIMIT :limit
    """, limit=limit)


def top_customers(db: Session, limit: int = 10) -> list[dict]:
    return _rows(db, """
        SELECT c.customer_name, c.segment,
               ROUND(SUM(f.revenue)::numeric, 2) AS revenue,
               COUNT(DISTINCT f.order_id)        AS orders
        FROM fact_sales f JOIN dim_customer c ON f.customer_key = c.customer_key
        GROUP BY c.customer_name, c.segment
        ORDER BY revenue DESC
        LIMIT :limit
    """, limit=limit)


def sales_by_region(db: Session) -> list[dict]:
    return _rows(db, """
        SELECT l.region,
               ROUND(SUM(f.revenue)::numeric, 2) AS revenue,
               ROUND(SUM(f.profit)::numeric, 2)  AS profit
        FROM fact_sales f JOIN dim_location l ON f.location_key = l.location_key
        GROUP BY l.region
        ORDER BY revenue DESC
    """)


def category_performance(db: Session) -> list[dict]:
    return _rows(db, """
        SELECT p.category,
               ROUND(SUM(f.revenue)::numeric, 2) AS revenue,
               ROUND(SUM(f.profit)::numeric, 2)  AS profit,
               SUM(f.quantity)                   AS units
        FROM fact_sales f JOIN dim_product p ON f.product_key = p.product_key
        GROUP BY p.category
        ORDER BY revenue DESC
    """)


def generate_insights(db: Session) -> list[dict]:
    """Rule-based observations derived from the warehouse.

    Deliberately NOT LLM-generated: these statements must be factually
    tied to the data. The LLM's role is explanation, not fact creation.
    """
    insights: list[dict] = []

    prods = top_products(db, limit=100)
    if prods:
        best = prods[0]
        insights.append({
            "type": "positive", "title": "Best-performing product",
            "detail": f"{best['product_name']} leads with Rs {float(best['revenue']):,.0f} "
                      f"in revenue across {int(best['units'])} units.",
        })
        weak = [p for p in prods if float(p["profit"] or 0) < 0]
        if weak:
            insights.append({
                "type": "negative", "title": "Products losing money",
                "detail": f"{len(weak)} product(s) are sold at a loss. Worst: "
                          f"{weak[-1]['product_name']} at Rs {float(weak[-1]['profit']):,.0f} profit.",
            })
        elif len(prods) > 3:
            worst = prods[-1]
            insights.append({
                "type": "warning", "title": "Weakest product",
                "detail": f"{worst['product_name']} contributes only "
                          f"Rs {float(worst['revenue']):,.0f} — review pricing or shelf space.",
            })

    regions = sales_by_region(db)
    if len(regions) > 1:
        insights.append({
            "type": "positive", "title": "Strongest region",
            "detail": f"{regions[0]['region']} generated Rs {float(regions[0]['revenue']):,.0f}, "
                      f"the highest of {len(regions)} regions.",
        })
        insights.append({
            "type": "warning", "title": "Region needing attention",
            "detail": f"{regions[-1]['region']} trails at Rs {float(regions[-1]['revenue']):,.0f}.",
        })

    months = monthly_sales(db)
    if len(months) >= 2:
        cur, prev = months[-1], months[-2]
        delta = float(cur["revenue"] or 0) - float(prev["revenue"] or 0)
        pct = (delta / float(prev["revenue"])) * 100 if float(prev["revenue"] or 0) else 0
        insights.append({
            "type": "positive" if delta >= 0 else "negative",
            "title": "Month-over-month movement",
            "detail": f"Revenue {'rose' if delta >= 0 else 'fell'} {abs(pct):.1f}% from "
                      f"{prev['month_name']} to {cur['month_name']} "
                      f"(Rs {abs(delta):,.0f}).",
        })

    cust = top_customers(db, limit=100)
    if cust:
        total = sum(float(c["revenue"] or 0) for c in cust)
        top5 = sum(float(c["revenue"] or 0) for c in cust[:5])
        if total:
            share = top5 / total * 100
            insights.append({
                "type": "warning" if share > 50 else "neutral",
                "title": "Customer concentration",
                "detail": f"The top 5 customers account for {share:.1f}% of revenue"
                          + (" — a concentration risk." if share > 50 else "."),
            })
    return insights
