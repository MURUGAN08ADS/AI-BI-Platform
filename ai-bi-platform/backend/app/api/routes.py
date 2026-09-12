"""REST API surface.

Route groups:
  /api/auth       register, login, me
  /api/upload     dataset upload -> ETL, upload history, ETL logs
  /api/analytics  KPI cards, charts, AI insights
  /api/chat       natural-language question -> SQL -> answer
  /api/forecast   revenue projection
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.analytics import kpis
from app.auth.security import (create_token, current_user, hash_password,
                               require_role, verify_password, ROLES)
from app.chatbot.nl2sql import ChatbotError, answer_question
from app.config import settings
from app.database.session import get_db
from app.etl.pipeline import EtlError, run_etl
from app.forecasting.forecast import forecast_revenue
from app.models.warehouse import AppUser, EtlLog, UploadBatch

router = APIRouter()


# ============================== schemas ==============================
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, description="At least 8 characters")
    role: str = "analyst"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    email: str


class ChatIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)


# ================================ auth ================================
@router.post("/auth/register", response_model=TokenOut, tags=["auth"])
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if body.role not in ROLES:
        raise HTTPException(400, f"Role must be one of: {', '.join(ROLES)}.")
    if db.execute(select(AppUser).where(AppUser.email == body.email)).scalar_one_or_none():
        raise HTTPException(409, "An account with that email already exists.")
    user = AppUser(email=body.email, password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    db.commit()
    return TokenOut(access_token=create_token(user.email, user.role),
                    role=user.role, email=user.email)


@router.post("/auth/login", response_model=TokenOut, tags=["auth"])
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.execute(select(AppUser).where(AppUser.email == body.email)).scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Email or password is incorrect.")
    return TokenOut(access_token=create_token(user.email, user.role),
                    role=user.role, email=user.email)


@router.get("/auth/me", tags=["auth"])
def me(user: AppUser = Depends(current_user)):
    return {"email": user.email, "role": user.role}


# =============================== upload ===============================
@router.post("/upload", tags=["upload"])
async def upload_dataset(file: UploadFile = File(...),
                         db: Session = Depends(get_db),
                         user: AppUser = Depends(require_role("admin", "analyst"))):
    """Upload a CSV/XLSX and run it through the ETL pipeline."""
    if not file.filename.lower().endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(400, "Upload a .csv or .xlsx file.")

    content = await file.read()
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(413, f"File is larger than the {settings.MAX_UPLOAD_MB} MB limit.")
    if not content:
        raise HTTPException(400, "The file is empty.")

    try:
        return run_etl(db, content, file.filename, user=user.email)
    except EtlError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/upload/history", tags=["upload"])
def upload_history(db: Session = Depends(get_db), user: AppUser = Depends(current_user)):
    batches = db.execute(
        select(UploadBatch).order_by(desc(UploadBatch.uploaded_at)).limit(50)
    ).scalars().all()
    return [{"batch_id": b.batch_id, "filename": b.filename, "rows_loaded": b.row_count,
             "rows_rejected": b.rows_rejected, "status": b.status, "message": b.message,
             "uploaded_by": b.uploaded_by, "uploaded_at": b.uploaded_at} for b in batches]


@router.get("/upload/{batch_id}/logs", tags=["upload"])
def batch_logs(batch_id: int, db: Session = Depends(get_db),
               user: AppUser = Depends(current_user)):
    logs = db.execute(
        select(EtlLog).where(EtlLog.batch_id == batch_id).order_by(EtlLog.log_id)
    ).scalars().all()
    return [{"stage": l.stage, "level": l.level, "message": l.message,
             "at": l.created_at} for l in logs]


# ============================== analytics ==============================
@router.get("/analytics/kpis", tags=["analytics"])
def get_kpis(db: Session = Depends(get_db), user: AppUser = Depends(current_user)):
    return kpis.kpi_summary(db)


@router.get("/analytics/monthly", tags=["analytics"])
def get_monthly(db: Session = Depends(get_db), user: AppUser = Depends(current_user)):
    return kpis.monthly_sales(db)


@router.get("/analytics/products", tags=["analytics"])
def get_products(limit: int = 10, db: Session = Depends(get_db),
                 user: AppUser = Depends(current_user)):
    return kpis.top_products(db, limit)


@router.get("/analytics/customers", tags=["analytics"])
def get_customers(limit: int = 10, db: Session = Depends(get_db),
                  user: AppUser = Depends(current_user)):
    return kpis.top_customers(db, limit)


@router.get("/analytics/regions", tags=["analytics"])
def get_regions(db: Session = Depends(get_db), user: AppUser = Depends(current_user)):
    return kpis.sales_by_region(db)


@router.get("/analytics/categories", tags=["analytics"])
def get_categories(db: Session = Depends(get_db), user: AppUser = Depends(current_user)):
    return kpis.category_performance(db)


@router.get("/analytics/insights", tags=["analytics"])
def get_insights(db: Session = Depends(get_db), user: AppUser = Depends(current_user)):
    return kpis.generate_insights(db)


# ================================ chat ================================
@router.post("/chat", tags=["chat"])
async def chat(body: ChatIn, user: AppUser = Depends(current_user)):
    """Ask the warehouse a question in plain English.

    The generated SQL is returned alongside the answer so the query is
    always auditable.
    """
    try:
        return await answer_question(body.question)
    except ChatbotError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


# ============================== forecast ==============================
@router.get("/forecast", tags=["forecast"])
def get_forecast(periods: int = 6, db: Session = Depends(get_db),
                 user: AppUser = Depends(current_user)):
    if not 1 <= periods <= 24:
        raise HTTPException(400, "Forecast horizon must be between 1 and 24 months.")
    return forecast_revenue(db, periods)
