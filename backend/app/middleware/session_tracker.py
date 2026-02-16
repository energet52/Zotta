"""Session activity tracking middleware.

Updates the `last_activity_at` timestamp on active sessions
for each authenticated request, debounced to avoid excessive DB writes.
"""

import time
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SessionTrackerMiddleware(BaseHTTPMiddleware):
    """Lightweight middleware that tracks request timestamps per session.

    The actual session update is handled inside get_current_user in auth_utils.py
    (updates UserSession.last_activity_at). This middleware serves as a hook point
    for future enhancements like request counting or rate limiting.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Add timing info for debugging/monitoring
        start = time.monotonic()
        response = await call_next(request)
        elapsed_ms = round((time.monotonic() - start) * 1000, 1)
        response.headers["X-Response-Time"] = f"{elapsed_ms}ms"
        return response
