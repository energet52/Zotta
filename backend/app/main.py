"""Zotta Lending Application - FastAPI Entry Point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.api import auth, loans, underwriter, verification, reports, whatsapp, payments, collections


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables on startup (dev only); in prod use Alembic migrations."""
    if settings.environment == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="Zotta Lending API",
    description="API for the Zotta consumer lending platform",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(loans.router, prefix="/api/loans", tags=["Loans"])
app.include_router(underwriter.router, prefix="/api/underwriter", tags=["Underwriter"])
app.include_router(verification.router, prefix="/api/verification", tags=["Verification"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(whatsapp.router, prefix="/api/whatsapp", tags=["WhatsApp"])
app.include_router(payments.router, prefix="/api/payments", tags=["Payments"])
app.include_router(collections.router, prefix="/api/collections", tags=["Collections"])


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "zotta-api", "version": "0.2.0"}
