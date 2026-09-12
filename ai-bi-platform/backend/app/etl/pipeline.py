"""ETL pipeline: raw spreadsheet -> validated -> star schema.

WORKFLOW
    extract    read CSV/XLSX into a DataFrame, fail fast on unreadable files
    transform  normalise headers, coerce types, drop duplicates, handle
               missing values, derive revenue/profit, reject bad rows
    load       upsert dimensions, resolve surrogate keys, bulk-insert facts
               inside ONE transaction so a partial file never lands

Design notes
  * Rejected rows are counted and logged rather than silently dropped —
    an analyst must be able to see that 12 of 5,000 rows were unusable.
  * The whole load runs in a single transaction. If row 4,999 fails, the
    warehouse is left exactly as it was before the upload.
"""
from __future__ import annotations

import hashlib
import io
import re
from datetime import date, datetime

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.warehouse import (DimCustomer, DimDate, DimLocation,
                                  DimProduct, EtlLog, FactSales, UploadBatch)

# Columns the pipeline understands. Source files vary wildly, so each
# canonical name maps to the aliases seen in the wild.
COLUMN_ALIASES: dict[str, list[str]] = {
    "order_id":      ["order_id", "orderid", "order", "invoice_id", "invoice"],
    "order_date":    ["order_date", "date", "orderdate", "transaction_date"],
    "customer_id":   ["customer_id", "customerid", "cust_id"],
    "customer_name": ["customer_name", "customer", "customername", "client"],
    "segment":       ["segment", "customer_segment"],
    "product_id":    ["product_id", "productid", "sku"],
    "product_name":  ["product_name", "product", "productname", "item"],
    "category":      ["category", "product_category"],
    "sub_category":  ["sub_category", "subcategory", "sub category"],
    "city":          ["city", "town"],
    "state":         ["state", "province"],
    "region":        ["region", "zone"],
    "quantity":      ["quantity", "qty", "units", "units_sold"],
    "unit_price":    ["unit_price", "price", "unitprice", "rate", "selling_price"],
    "discount":      ["discount", "discount_pct", "discount_percent"],
    "cost":          ["cost", "unit_cost", "cogs"],
}

REQUIRED = ["order_date", "product_name", "quantity", "unit_price"]


class EtlError(Exception):
    """Raised when a file cannot be processed at all."""


# ------------------------------------------------------------------
# EXTRACT
# ------------------------------------------------------------------
def extract(content: bytes, filename: str) -> pd.DataFrame:
    """Read raw bytes into a DataFrame based on the file extension."""
    name = filename.lower()
    try:
        if name.endswith(".csv"):
            return pd.read_csv(io.BytesIO(content))
        if name.endswith((".xlsx", ".xls")):
            return pd.read_excel(io.BytesIO(content))
    except Exception as exc:  # noqa: BLE001 - surface any parse failure clearly
        raise EtlError(f"Could not read {filename}: {exc}") from exc
    raise EtlError("Unsupported file type. Upload a .csv or .xlsx file.")


def file_hash(content: bytes) -> str:
    """SHA-256 of the raw bytes — used to reject duplicate uploads."""
    return hashlib.sha256(content).hexdigest()


# ------------------------------------------------------------------
# TRANSFORM
# ------------------------------------------------------------------
def _normalise_headers(df: pd.DataFrame) -> pd.DataFrame:
    """lower_snake_case every column, then map known aliases to canonical names."""
    df = df.copy()
    df.columns = [re.sub(r"[^a-z0-9]+", "_", str(c).strip().lower()).strip("_")
                  for c in df.columns]
    rename: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for col in df.columns:
            if col in aliases and col != canonical:
                rename[col] = canonical
    return df.rename(columns=rename)


def transform(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Clean and enrich. Returns (clean_df, warnings)."""
    warnings: list[str] = []
    df = _normalise_headers(df)

    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise EtlError(
            f"Missing required column(s): {', '.join(missing)}. "
            f"Found: {', '.join(df.columns)}"
        )

    before = len(df)
    df = df.drop_duplicates()
    if len(df) < before:
        warnings.append(f"Removed {before - len(df)} duplicate rows.")

    # --- types ---
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce", dayfirst=True)
    for col in ("quantity", "unit_price", "discount", "cost"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # --- defaults for optional columns ---
    if "discount" not in df.columns:
        df["discount"] = 0.0
    if "cost" not in df.columns:
        # No cost column: assume a 70% cost ratio so profit is still meaningful.
        df["cost"] = df["unit_price"] * 0.7
        warnings.append("No cost column found; profit estimated at a 70% cost ratio.")
    for col, default in (("order_id", ""), ("customer_id", ""), ("customer_name", "Unknown"),
                         ("segment", "Unspecified"), ("product_id", ""), ("category", "Uncategorised"),
                         ("sub_category", ""), ("city", "Unknown"), ("state", ""), ("region", "Unknown")):
        if col not in df.columns:
            df[col] = default

    # Discounts given as 0-100 are rescaled to 0-1.
    if df["discount"].max(skipna=True) is not None and df["discount"].max(skipna=True) > 1:
        df["discount"] = df["discount"] / 100.0
        warnings.append("Discount values looked like percentages; rescaled to 0-1.")

    # --- reject unusable rows ---
    bad = (df["order_date"].isna() | df["quantity"].isna() | df["unit_price"].isna()
           | (df["quantity"] < 0) | (df["unit_price"] < 0))
    rejected = int(bad.sum())
    if rejected:
        warnings.append(f"Rejected {rejected} rows with invalid date, quantity or price.")
    df = df[~bad].copy()
    if df.empty:
        raise EtlError("No valid rows remained after cleaning.")

    df["discount"] = df["discount"].fillna(0).clip(0, 1)
    df["cost"] = df["cost"].fillna(0)

    # --- natural keys when the source omits them ---
    df["customer_id"] = df.apply(
        lambda r: str(r["customer_id"]).strip() or f"CUST-{abs(hash(r['customer_name'])) % 10**8}",
        axis=1)
    df["product_id"] = df.apply(
        lambda r: str(r["product_id"]).strip() or f"PROD-{abs(hash(r['product_name'])) % 10**8}",
        axis=1)

    # --- derived measures ---
    df["revenue"] = (df["quantity"] * df["unit_price"] * (1 - df["discount"])).round(2)
    df["total_cost"] = (df["quantity"] * df["cost"]).round(2)
    df["profit"] = (df["revenue"] - df["total_cost"]).round(2)
    df["date_key"] = df["order_date"].dt.strftime("%Y%m%d").astype(int)

    df.attrs["rejected"] = rejected
    return df, warnings


# ------------------------------------------------------------------
# LOAD
# ------------------------------------------------------------------
def _upsert_dates(db: Session, dates: set[pd.Timestamp]) -> None:
    existing = {d for (d,) in db.execute(select(DimDate.date_key))}
    rows = []
    for ts in dates:
        key = int(ts.strftime("%Y%m%d"))
        if key in existing:
            continue
        existing.add(key)
        rows.append(DimDate(
            date_key=key, full_date=ts.date(), year=ts.year,
            quarter=(ts.month - 1) // 3 + 1, month=ts.month,
            month_name=ts.strftime("%B"), day=ts.day,
            day_name=ts.strftime("%A"), is_weekend=ts.weekday() >= 5,
        ))
    db.add_all(rows)
    db.flush()


def _upsert_dimension(db: Session, model, natural_col: str, records: list[dict]) -> dict[str, int]:
    """Insert any unseen dimension members, return {natural_key: surrogate_key}."""
    pk = model.__mapper__.primary_key[0].name
    existing = {getattr(o, natural_col): getattr(o, pk) for o in db.execute(select(model)).scalars()}
    new = [r for r in records if r[natural_col] not in existing]
    if new:
        db.add_all([model(**r) for r in new])
        db.flush()
        for o in db.execute(select(model)).scalars():
            existing[getattr(o, natural_col)] = getattr(o, pk)
    return existing


def load(db: Session, df: pd.DataFrame, batch_id: int) -> int:
    """Load a cleaned DataFrame into the star schema. Caller owns the transaction."""
    _upsert_dates(db, set(df["order_date"].unique().tolist()))

    cust_records = (df[["customer_id", "customer_name", "segment"]]
                    .drop_duplicates("customer_id").to_dict("records"))
    cust_map = _upsert_dimension(db, DimCustomer, "customer_id", cust_records)

    prod_records = (df[["product_id", "product_name", "category", "sub_category"]]
                    .drop_duplicates("product_id").to_dict("records"))
    prod_map = _upsert_dimension(db, DimProduct, "product_id", prod_records)

    # Location has a composite natural key, so it is resolved separately.
    loc_rows = df[["city", "state", "region"]].drop_duplicates().to_dict("records")
    loc_map: dict[tuple, int] = {
        (o.city, o.state, o.region): o.location_key
        for o in db.execute(select(DimLocation)).scalars()
    }
    fresh = [r for r in loc_rows if (r["city"], r["state"], r["region"]) not in loc_map]
    if fresh:
        db.add_all([DimLocation(**r) for r in fresh])
        db.flush()
        loc_map = {(o.city, o.state, o.region): o.location_key
                   for o in db.execute(select(DimLocation)).scalars()}

    facts = [
        FactSales(
            date_key=int(r.date_key),
            customer_key=cust_map[r.customer_id],
            product_key=prod_map[r.product_id],
            location_key=loc_map[(r.city, r.state, r.region)],
            batch_id=batch_id,
            order_id=str(r.order_id) or None,
            quantity=int(r.quantity),
            unit_price=float(r.unit_price),
            discount=float(r.discount),
            revenue=float(r.revenue),
            cost=float(r.total_cost),
            profit=float(r.profit),
        )
        for r in df.itertuples(index=False)
    ]
    db.bulk_save_objects(facts)
    return len(facts)


# ------------------------------------------------------------------
# ORCHESTRATION
# ------------------------------------------------------------------
def log(db: Session, batch_id: int | None, stage: str, level: str, message: str) -> None:
    db.add(EtlLog(batch_id=batch_id, stage=stage, level=level, message=message))


def run_etl(db: Session, content: bytes, filename: str, user: str | None = None) -> dict:
    """Full pipeline. Commits on success, rolls back everything on failure."""
    digest = file_hash(content)
    dup = db.execute(select(UploadBatch).where(UploadBatch.file_hash == digest)).scalar_one_or_none()
    if dup:
        raise EtlError(f"This file was already uploaded on {dup.uploaded_at:%d %b %Y} (batch {dup.batch_id}).")

    batch = UploadBatch(filename=filename, file_hash=digest, uploaded_by=user, status="pending")
    db.add(batch)
    db.flush()

    try:
        raw = extract(content, filename)
        log(db, batch.batch_id, "extract", "info", f"Read {len(raw)} rows from {filename}.")

        clean, warnings = transform(raw)
        for w in warnings:
            log(db, batch.batch_id, "transform", "warning", w)
        log(db, batch.batch_id, "transform", "info", f"{len(clean)} rows passed validation.")

        inserted = load(db, clean, batch.batch_id)
        batch.row_count = inserted
        batch.rows_rejected = int(clean.attrs.get("rejected", 0))
        batch.status = "success"
        batch.message = "; ".join(warnings) or "Loaded cleanly."
        log(db, batch.batch_id, "load", "info", f"Inserted {inserted} fact rows.")

        db.commit()
        return {
            "batch_id": batch.batch_id, "filename": filename, "rows_loaded": inserted,
            "rows_rejected": batch.rows_rejected, "warnings": warnings, "status": "success",
        }
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        # Record the failure in its own transaction so the audit trail survives.
        failed = UploadBatch(filename=filename, file_hash=digest + "-failed"[:0] + digest[:0] or digest,
                             uploaded_by=user, status="failed", message=str(exc)[:500])
        try:
            db.add(failed)
            db.commit()
        except Exception:
            db.rollback()
        raise EtlError(str(exc)) from exc
