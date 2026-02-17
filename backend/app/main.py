"""Zotta Lending Application - FastAPI Entry Point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import engine, Base, async_session
from app.middleware.error_capture import ErrorCaptureMiddleware
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
    error_logs,
    scorecards,
    users,
    collection_sequences,
    queue,
    pre_approval,
)
from app.seed_catalog import seed_catalog_data
from app.seed_gl import seed_gl_data
from app.seed_scorecard import seed_scorecard_data
from app.seed_sector import seed_sector_data
from app.seed_users import seed_user_management


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
        async with async_session() as db:
            await seed_scorecard_data(db)
        async with async_session() as db:
            await seed_sector_data(db)
        async with async_session() as db:
            await seed_user_management(db)
    yield


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Zotta Lending API",
    description="API for the Zotta consumer lending platform",
    version="0.2.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Security headers middleware ──────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds standard security headers to every response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if settings.environment != "development":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; connect-src 'self'"
            )
        return response


# Error capture middleware (outermost — catches everything)
app.add_middleware(ErrorCaptureMiddleware)

# Security headers
app.add_middleware(SecurityHeadersMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
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
app.include_router(error_logs.router, prefix="/api/error-logs", tags=["Error Monitoring"])
app.include_router(scorecards.router, prefix="/api/scorecards", tags=["Scorecards"])
app.include_router(users.router, prefix="/api/users", tags=["User Management"])
app.include_router(collection_sequences.router, tags=["Collection Sequences"])
app.include_router(queue.router, prefix="/api/queue", tags=["Queue Management"])
app.include_router(pre_approval.router, prefix="/api/pre-approval", tags=["Pre-Approval"])


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "zotta-api", "version": "0.2.0"}
