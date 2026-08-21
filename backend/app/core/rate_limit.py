"""Redis-backed protection for authentication and answer submission endpoints."""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.cache import rate_limit_hit


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        if request.method == "POST" and path in ("/api/auth/login", "/api/auth/register", "/api/auth/refresh"):
            limit, window, scope = 12, 60, "auth"
        elif request.method == "POST" and path.startswith("/api/learning/problems/") and path.endswith("/submit"):
            limit, window, scope = 90, 60, "submission"
        else:
            return await call_next(request)
        client_ip = request.client.host if request.client else "unknown"
        allowed, remaining = await rate_limit_hit(f"rate:{scope}:{client_ip}", limit, window)
        if not allowed:
            return JSONResponse({"detail": "Too many requests. Please slow down."}, status_code=429, headers={"Retry-After": str(window)})
        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
