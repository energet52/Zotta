"""FastAPI middleware that captures unhandled exceptions and logs them to the DB.

Every 5xx response is automatically recorded in the error_logs table
so admins can monitor system health from the UI.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.models.error_log import ErrorSeverity
from app.services.error_logger import log_error_standalone

logger = logging.getLogger("zotta.middleware")

# Paths we don't want to capture request bodies for (security)
_SENSITIVE_PATHS = {
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/refresh",
    "/api/auth/change-password",
    "/api/auth/mfa/setup",
    "/api/auth/mfa/verify",
    "/api/auth/mfa/confirm",
    "/api/payments",
}

# Max body size to capture (avoid storing huge payloads)
_MAX_BODY_SIZE = 4096


class ErrorCaptureMiddleware(BaseHTTPMiddleware):
    """Catches unhandled exceptions, returns 500, and persists the error."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.time()
        request_body: Optional[str] = None

        # Try to read request body for context (skip sensitive endpoints)
        _is_sensitive = any(request.url.path.startswith(p) for p in _SENSITIVE_PATHS)
        if request.method in ("POST", "PUT", "PATCH") and not _is_sensitive:
            try:
                body_bytes = await request.body()
                if len(body_bytes) <= _MAX_BODY_SIZE:
                    request_body = body_bytes.decode("utf-8", errors="replace")
            except Exception:
                pass

        # Extract user info from auth if available
        user_id: Optional[int] = None
        user_email: Optional[str] = None
        try:
            from app.config import settings
            from jose import jwt as jose_jwt
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                payload = jose_jwt.decode(token, settings.secret_key, algorithms=["HS256"])
                user_id = int(payload.get("sub", 0)) or None
                user_email = payload.get("email") or None
        except Exception:
            pass  # auth extraction is best-effort

        ip_address = request.client.host if request.client else None

        try:
            response = await call_next(request)
            elapsed_ms = round((time.time() - start) * 1000, 2)

            # Log 5xx errors as ERROR severity
            if response.status_code >= 500:
                await log_error_standalone(
                    Exception(f"HTTP {response.status_code} on {request.method} {request.url.path}"),
                    severity=ErrorSeverity.ERROR,
                    module="middleware.error_capture",
                    function_name="dispatch",
                    request_method=request.method,
                    request_path=str(request.url.path),
                    request_body=request_body,
                    status_code=response.status_code,
                    response_time_ms=elapsed_ms,
                    user_id=user_id,
                    user_email=user_email,
                    ip_address=ip_address,
                )
            # Log 4xx client errors as WARNING severity (skip 401/403 auth noise)
            elif response.status_code >= 400 and response.status_code not in (401, 403):
                await log_error_standalone(
                    Exception(f"HTTP {response.status_code} on {request.method} {request.url.path}"),
                    severity=ErrorSeverity.WARNING,
                    module="middleware.error_capture",
                    function_name="dispatch",
                    request_method=request.method,
                    request_path=str(request.url.path),
                    request_body=request_body,
                    status_code=response.status_code,
                    response_time_ms=elapsed_ms,
                    user_id=user_id,
                    user_email=user_email,
                    ip_address=ip_address,
                )

            return response

        except Exception as exc:
            elapsed_ms = round((time.time() - start) * 1000, 2)

            # Determine severity
            from fastapi import HTTPException
            if isinstance(exc, HTTPException) and exc.status_code < 500:
                # 4xx errors from HTTPException — don't log these as errors
                raise

            severity = ErrorSeverity.CRITICAL if "database" in str(exc).lower() else ErrorSeverity.ERROR

            await log_error_standalone(
                exc,
                severity=severity,
                module="middleware.error_capture",
                request_method=request.method,
                request_path=str(request.url.path),
                request_body=request_body,
                status_code=500,
                response_time_ms=elapsed_ms,
                user_id=user_id,
                user_email=user_email,
                ip_address=ip_address,
            )

            logger.exception("Unhandled exception on %s %s", request.method, request.url.path)

            return JSONResponse(
                status_code=500,
                content={"detail": "Internal Server Error"},
            )
