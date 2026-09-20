"""Application entry point.

Run:  uvicorn app.main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import settings
from app.database.session import Base, engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
log = logging.getLogger("bi-platform")

app = FastAPI(
    title="AI-Powered BI & Data Warehouse Platform",
    description=(
        "Upload business data, run it through an ETL pipeline into a star-schema "
        "warehouse, explore it on dashboards, and ask questions in plain English."
    ),
    version="1.0.0",
)

# The React dev server runs on a different origin during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        settings.FRONTEND_URL,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.on_event("startup")
def on_startup() -> None:
    """Create tables if they are missing.

    schema.sql remains the source of truth (it also creates indexes and
    the read-only role); this is a convenience so the API still starts
    against a bare database.
    """
    try:
        Base.metadata.create_all(bind=engine)
        log.info("Database ready.")
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not verify schema at startup: %s", exc)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    """Never leak a stack trace to the client; log it instead."""
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500,
                        content={"detail": "Something went wrong on our side."})


@app.get("/api/health", tags=["system"])
def health():
    return {"status": "ok"}
