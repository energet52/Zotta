"""Error Logs API — admin-only endpoints for monitoring application errors."""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, desc, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserRole
from app.models.error_log import ErrorLog, ErrorSeverity
from app.auth_utils import require_roles

logger = logging.getLogger(__name__)
router = APIRouter()

ADMIN_ROLES = (UserRole.ADMIN,)


# ── Schemas ─────────────────────────────────────────────────

class ErrorLogResolveRequest(BaseModel):
    resolution_notes: Optional[str] = None


class ErrorLogBulkResolveRequest(BaseModel):
    ids: list[int]
    resolution_notes: Optional[str] = None


# ── List / Search ───────────────────────────────────────────

@router.get("")
async def list_error_logs(
    severity: Optional[str] = Query(None),
    resolved: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    module: Optional[str] = Query(None),
    path: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """List error logs with filtering and pagination."""
    q = select(ErrorLog).order_by(desc(ErrorLog.created_at))

    if severity:
        q = q.where(ErrorLog.severity == ErrorSeverity(severity))
    if resolved is not None:
        q = q.where(ErrorLog.resolved == resolved)
    if search:
        pattern = f"%{search}%"
        q = q.where(
            ErrorLog.message.ilike(pattern)
            | ErrorLog.error_type.ilike(pattern)
            | ErrorLog.request_path.ilike(pattern)
            | ErrorLog.module.ilike(pattern)
        )
    if module:
        q = q.where(ErrorLog.module.ilike(f"%{module}%"))
    if path:
        q = q.where(ErrorLog.request_path.ilike(f"%{path}%"))

    # Count
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Paginate
    result = await db.execute(q.offset(offset).limit(limit))
    logs = result.scalars().all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [_log_to_dict(log, include_traceback=False) for log in logs],
    }


# ── Summary / Stats ────────────────────────────────────────

@router.get("/stats")
async def error_stats(
    hours: int = Query(24, ge=1, le=720),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get error statistics for the dashboard."""
    from datetime import timedelta

    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    # Counts by severity
    severity_q = await db.execute(
        select(
            ErrorLog.severity,
            func.count(ErrorLog.id),
        )
        .where(ErrorLog.created_at >= since)
        .group_by(ErrorLog.severity)
    )
    by_severity = {row[0].value if hasattr(row[0], "value") else row[0]: row[1] for row in severity_q.all()}

    # Total unresolved
    unresolved_q = await db.execute(
        select(func.count(ErrorLog.id)).where(ErrorLog.resolved == False)
    )
    unresolved = unresolved_q.scalar() or 0

    # Total in period
    total_q = await db.execute(
        select(func.count(ErrorLog.id)).where(ErrorLog.created_at >= since)
    )
    total_in_period = total_q.scalar() or 0

    # Top error types
    top_types_q = await db.execute(
        select(
            ErrorLog.error_type,
            func.count(ErrorLog.id).label("cnt"),
        )
        .where(ErrorLog.created_at >= since)
        .group_by(ErrorLog.error_type)
        .order_by(desc("cnt"))
        .limit(10)
    )
    top_types = [{"error_type": row[0], "count": row[1]} for row in top_types_q.all()]

    # Top paths
    top_paths_q = await db.execute(
        select(
            ErrorLog.request_path,
            func.count(ErrorLog.id).label("cnt"),
        )
        .where(ErrorLog.created_at >= since, ErrorLog.request_path.isnot(None))
        .group_by(ErrorLog.request_path)
        .order_by(desc("cnt"))
        .limit(10)
    )
    top_paths = [{"path": row[0], "count": row[1]} for row in top_paths_q.all()]

    # Errors per hour (for chart)
    hourly_q = await db.execute(
        select(
            func.date_trunc("hour", ErrorLog.created_at).label("hour"),
            func.count(ErrorLog.id).label("cnt"),
        )
        .where(ErrorLog.created_at >= since)
        .group_by("hour")
        .order_by("hour")
    )
    hourly = [{"hour": row[0].isoformat() if row[0] else None, "count": row[1]} for row in hourly_q.all()]

    return {
        "period_hours": hours,
        "total_in_period": total_in_period,
        "unresolved": unresolved,
        "by_severity": by_severity,
        "top_error_types": top_types,
        "top_paths": top_paths,
        "hourly": hourly,
    }


# ── Detail ──────────────────────────────────────────────────

@router.get("/{error_id}")
async def get_error_log(
    error_id: int,
    user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Get a single error log with full traceback."""
    q = await db.execute(select(ErrorLog).where(ErrorLog.id == error_id))
    log = q.scalar_one_or_none()
    if not log:
        raise HTTPException(404, "Error log not found")
    return _log_to_dict(log, include_traceback=True)


# ── Resolve ─────────────────────────────────────────────────

@router.patch("/{error_id}/resolve")
async def resolve_error(
    error_id: int,
    body: ErrorLogResolveRequest,
    user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Mark an error as resolved."""
    q = await db.execute(select(ErrorLog).where(ErrorLog.id == error_id))
    log = q.scalar_one_or_none()
    if not log:
        raise HTTPException(404, "Error log not found")

    log.resolved = True
    log.resolved_by = user.id
    log.resolved_at = datetime.now(timezone.utc)
    log.resolution_notes = body.resolution_notes
    await db.flush()
    return _log_to_dict(log)


@router.patch("/{error_id}/unresolve")
async def unresolve_error(
    error_id: int,
    user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Mark a resolved error as unresolved."""
    q = await db.execute(select(ErrorLog).where(ErrorLog.id == error_id))
    log = q.scalar_one_or_none()
    if not log:
        raise HTTPException(404, "Error log not found")

    log.resolved = False
    log.resolved_by = None
    log.resolved_at = None
    log.resolution_notes = None
    await db.flush()
    return _log_to_dict(log)


# ── Bulk resolve ────────────────────────────────────────────

@router.post("/bulk-resolve")
async def bulk_resolve(
    body: ErrorLogBulkResolveRequest,
    user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Resolve multiple errors at once."""
    q = await db.execute(
        select(ErrorLog).where(ErrorLog.id.in_(body.ids))
    )
    logs = q.scalars().all()
    now = datetime.now(timezone.utc)
    for log in logs:
        log.resolved = True
        log.resolved_by = user.id
        log.resolved_at = now
        log.resolution_notes = body.resolution_notes
    await db.flush()
    return {"resolved": len(logs)}


# ── Delete old logs ─────────────────────────────────────────

@router.delete("/cleanup")
async def cleanup_old_logs(
    days: int = Query(90, ge=7, le=365),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Delete resolved error logs older than N days."""
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    q = await db.execute(
        select(ErrorLog).where(
            ErrorLog.resolved == True,
            ErrorLog.created_at < cutoff,
        )
    )
    old_logs = q.scalars().all()
    count = len(old_logs)
    for log in old_logs:
        await db.delete(log)
    await db.flush()
    return {"deleted": count, "cutoff_days": days}


# ── Serializer ──────────────────────────────────────────────

def _safe_text(value: Optional[str], *, max_len: Optional[int] = None) -> Optional[str]:
    if value is None:
        return None
    cleaned = "".join(ch if (ch >= " " or ch in "\n\r\t") else " " for ch in value)
    return cleaned[:max_len] if max_len is not None else cleaned


def _log_to_dict(log: ErrorLog, *, include_traceback: bool = True) -> dict:
    return {
        "id": log.id,
        "severity": log.severity.value if hasattr(log.severity, "value") else log.severity,
        "error_type": log.error_type,
        "message": _safe_text(log.message, max_len=2000),
        "traceback": _safe_text(log.traceback, max_len=10000) if include_traceback else None,
        "module": _safe_text(log.module, max_len=300),
        "function_name": _safe_text(log.function_name, max_len=200),
        "line_number": log.line_number,
        "request_method": _safe_text(log.request_method, max_len=10),
        "request_path": _safe_text(log.request_path, max_len=500),
        "request_body": _safe_text(log.request_body, max_len=5000),
        "status_code": log.status_code,
        "response_time_ms": log.response_time_ms,
        "user_id": log.user_id,
        "user_email": _safe_text(log.user_email, max_len=200),
        "ip_address": _safe_text(log.ip_address, max_len=45),
        "resolved": log.resolved,
        "resolved_by": log.resolved_by,
        "resolved_at": log.resolved_at.isoformat() if log.resolved_at else None,
        "resolution_notes": _safe_text(log.resolution_notes, max_len=5000),
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }
