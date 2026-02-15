"""Zotta Lending Application - FastAPI Entry Point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base, async_session
from app.api import (
    auth,
    loans,
    underwriter,
    verification,
    reports,
    whatsapp,
    payments,
    collections,
    admin,
    catalog,
    conversations,
    customers,
    gl,
    sector_analysis,
)
from app.seed_catalog import seed_catalog_data
from app.seed_gl import seed_gl_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables on startup (dev only); in prod use Alembic migrations."""
    if settings.environment == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_session() as db:
            await seed_catalog_data(db)
        async with async_session() as db:
            await seed_gl_data(db)
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
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(catalog.router, prefix="/api/catalog", tags=["Catalog"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["Conversations"])
app.include_router(customers.router, prefix="/api/customers", tags=["Customer 360"])
app.include_router(gl.router, prefix="/api/gl", tags=["General Ledger"])
app.include_router(sector_analysis.router, prefix="/api/sector-analysis", tags=["Sector Analysis"])


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "zotta-api", "version": "0.2.0"}
