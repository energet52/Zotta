"""Centralised error logging — captures exceptions to DB and Python logger.

Usage:
    # 1. As a function call in any try/except:
    from app.services.error_logger import log_error
    try:
        ...
    except Exception as e:
        await log_error(e, db=db, module="my_module", function_name="my_func")

    # 2. Middleware captures unhandled request errors automatically.
"""

from __future__ import annotations

import logging
import traceback as tb_module
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.error_log import ErrorLog, ErrorSeverity

logger = logging.getLogger("zotta.errors")


async def log_error(
    exc: Exception,
    *,
    db: Optional[AsyncSession] = None,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    module: Optional[str] = None,
    function_name: Optional[str] = None,
    line_number: Optional[int] = None,
    request_method: Optional[str] = None,
    request_path: Optional[str] = None,
    request_body: Optional[str] = None,
    status_code: Optional[int] = None,
    response_time_ms: Optional[float] = None,
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Optional[ErrorLog]:
    """Log an exception to the database and Python logger.

    If no db session is available, falls back to Python logging only.
    Returns the created ErrorLog row (or None if DB write failed/skipped).
    """

    error_type = type(exc).__name__
    message = str(exc)[:2000]  # cap message length
    traceback_str = "".join(tb_module.format_exception(type(exc), exc, exc.__traceback__))

    # Auto-detect module/function/line from traceback if not provided
    if exc.__traceback__ and not module:
        frame = exc.__traceback__
        while frame.tb_next:
            frame = frame.tb_next
        module = module or frame.tb_frame.f_code.co_filename
        function_name = function_name or frame.tb_frame.f_code.co_name
        line_number = line_number or frame.tb_lineno

    # Always log to Python logger
    log_msg = f"[{severity.value.upper()}] {error_type}: {message}"
    if request_path:
        log_msg = f"{request_method or '?'} {request_path} -> {log_msg}"
    logger.error(log_msg, exc_info=exc)

    if db is None:
        return None

    try:
        entry = ErrorLog(
            severity=severity,
            error_type=error_type,
            message=message,
            traceback=traceback_str[:10000],  # cap traceback
            module=module[:300] if module else None,
            function_name=function_name[:200] if function_name else None,
            line_number=line_number,
            request_method=request_method,
            request_path=request_path[:500] if request_path else None,
            request_body=request_body[:5000] if request_body else None,
            status_code=status_code,
            response_time_ms=response_time_ms,
            user_id=user_id,
            user_email=user_email,
            ip_address=ip_address,
        )
        db.add(entry)
        await db.flush()
        return entry
    except Exception as db_err:
        # Never let error-logging itself crash the app
        logger.warning("Failed to persist error log to DB: %s", db_err)
        return None


async def log_error_standalone(
    exc: Exception,
    *,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    module: Optional[str] = None,
    function_name: Optional[str] = None,
    request_method: Optional[str] = None,
    request_path: Optional[str] = None,
    request_body: Optional[str] = None,
    status_code: Optional[int] = None,
    response_time_ms: Optional[float] = None,
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Optional[ErrorLog]:
    """Log an error using a standalone DB session (for middleware use)."""
    from app.database import async_session

    try:
        async with async_session() as db:
            entry = await log_error(
                exc,
                db=db,
                severity=severity,
                module=module,
                function_name=function_name,
                request_method=request_method,
                request_path=request_path,
                request_body=request_body,
                status_code=status_code,
                response_time_ms=response_time_ms,
                user_id=user_id,
                user_email=user_email,
                ip_address=ip_address,
            )
            await db.commit()
            return entry
    except Exception as db_err:
        logger.warning("Failed standalone error log: %s", db_err)
        return None
