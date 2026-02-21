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


def _sanitize_text(value: object, *, max_len: Optional[int] = None) -> str:
    """Normalize control characters before persisting/serializing text."""
    text = str(value)
    # Keep common whitespace but strip other control chars.
    text = "".join(ch if (ch >= " " or ch in "\n\r\t") else " " for ch in text)
    if max_len is not None:
        return text[:max_len]
    return text


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
    message = _sanitize_text(exc, max_len=2000)
    traceback_str = _sanitize_text(
        "".join(tb_module.format_exception(type(exc), exc, exc.__traceback__)),
        max_len=10000,
    )

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
            traceback=traceback_str,
            module=_sanitize_text(module, max_len=300) if module else None,
            function_name=_sanitize_text(function_name, max_len=200) if function_name else None,
            line_number=line_number,
            request_method=request_method,
            request_path=_sanitize_text(request_path, max_len=500) if request_path else None,
            request_body=_sanitize_text(request_body, max_len=5000) if request_body else None,
            status_code=status_code,
            response_time_ms=response_time_ms,
            user_id=user_id,
            user_email=_sanitize_text(user_email, max_len=200) if user_email else None,
            ip_address=_sanitize_text(ip_address, max_len=45) if ip_address else None,
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
