"""Zotta Lending Application - FastAPI Entry Point."""

import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

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
    strategies,
)
from app.seed_catalog import seed_catalog_data
from app.seed_gl import seed_gl_data
from app.seed_scorecard import seed_scorecard_data
from app.seed_sector import seed_sector_data
from app.seed_users import seed_user_management


async def _add_missing_columns(conn):
    """Add columns to existing tables that create_all cannot handle.

    Uses IF NOT EXISTS so it is safe to run repeatedly.
    """
    stmts = [
        "ALTER TABLE credit_products ADD COLUMN IF NOT EXISTS decision_tree_id INTEGER REFERENCES decision_trees(id)",
        "ALTER TABLE credit_products ADD COLUMN IF NOT EXISTS default_strategy_id INTEGER REFERENCES decision_strategies(id)",
        "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS strategy_id INTEGER REFERENCES decision_strategies(id)",
        "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS tree_version INTEGER",
        "ALTER TABLE decisions ADD COLUMN IF NOT EXISTS routing_path JSONB",
    ]
    from sqlalchemy import text
    for stmt in stmts:
        await conn.execute(text(stmt))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables on startup (dev only); in prod use Alembic migrations."""
    if settings.environment == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await _add_missing_columns(conn)
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
        async with async_session() as db:
            await _ensure_fallback_strategy(db)
    yield


async def _ensure_fallback_strategy(db):
    """Create the fallback default strategy if it doesn't exist."""
    try:
        from sqlalchemy import select
        from app.models.strategy import (
            DecisionStrategy, StrategyStatus, EvaluationMode,
            DecisionTree, TreeStatus, DecisionTreeNode, NodeType,
            Assessment,
        )
        from app.services.decision_engine.rules import RULES_REGISTRY
        from app.models.catalog import CreditProduct
        from sqlalchemy import func as sa_func

        existing = await db.execute(
            select(DecisionStrategy).where(DecisionStrategy.is_fallback == True)
        )
        if existing.scalar_one_or_none():
            return

        strategy = DecisionStrategy(
            name="Default Fallback Strategy",
            description="Automatically applied to products without a custom strategy. Uses the standard business rules template.",
            evaluation_mode=EvaluationMode.DUAL_PATH,
            status=StrategyStatus.ACTIVE,
            version=1,
            is_fallback=True,
        )
        db.add(strategy)
        await db.flush()

        products_q = await db.execute(select(sa_func.min(CreditProduct.id)))
        product_id = products_q.scalar() or 1

        tree_ver_q = await db.execute(
            select(sa_func.max(DecisionTree.version)).where(DecisionTree.product_id == product_id)
        )
        tree_ver = (tree_ver_q.scalar() or 0) + 1

        tree = DecisionTree(
            product_id=product_id,
            name="Default Fallback - Decision Tree",
            description="Auto-created fallback tree",
            version=tree_ver,
            status=TreeStatus.ACTIVE,
        )
        db.add(tree)
        await db.flush()

        root = DecisionTreeNode(
            tree_id=tree.id, node_key="application_received",
            node_type=NodeType.ANNOTATION, label="Application Received",
            is_root=True, position_x=300, position_y=50,
        )
        db.add(root)
        await db.flush()

        assess_node = DecisionTreeNode(
            tree_id=tree.id, node_key="default_assessment",
            node_type=NodeType.ASSESSMENT, label="Standard Assessment",
            parent_node_id=root.id, branch_label="evaluate",
            is_root=False, position_x=300, position_y=200,
        )
        db.add(assess_node)
        await db.flush()

        template_rules = []
        for idx, (_, rule_def) in enumerate(RULES_REGISTRY.items(), 1):
            seq_id = f"R{idx:02d}"
            template_rules.append({
                "rule_id": seq_id, "name": rule_def.get("name", ""),
                "field": rule_def.get("field", ""),
                "operator": rule_def.get("operator", "gte"),
                "threshold": rule_def.get("threshold"),
                "severity": rule_def.get("severity", "hard"),
                "outcome": rule_def.get("outcome", "decline"),
                "reason_code": seq_id,
                "enabled": rule_def.get("enabled", True),
            })

        assessment = Assessment(
            strategy_id=strategy.id, name="Standard Business Rules",
            description="Default assessment with all standard R01-R19 rules",
            rules=template_rules,
        )
        db.add(assessment)
        await db.flush()

        assess_node.assessment_id = assessment.id
        strategy.decision_tree_id = tree.id
        await db.commit()
        logger.info("Created fallback strategy id=%s", strategy.id)
    except Exception as e:
        logger.warning("Fallback strategy creation skipped: %s", e)
        await db.rollback()


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
app.include_router(strategies.router, prefix="/api", tags=["Decision Strategy Management"])


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "zotta-api", "version": "0.2.0"}
