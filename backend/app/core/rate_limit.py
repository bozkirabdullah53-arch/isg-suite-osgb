from collections import defaultdict, deque
from time import monotonic
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class SimpleRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 120):
        super().__init__(app)
        self.limit = requests_per_minute
        self.hits = defaultdict(deque)

    async def dispatch(self, request, call_next):
        client = request.client.host if request.client else "unknown"
        key = f"{client}:{request.url.path}"
        now = monotonic()
        window = self.hits[key]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= self.limit:
            return JSONResponse(
                {"detail": "Çok fazla istek gönderildi. Lütfen kısa süre sonra tekrar deneyin."},
                status_code=429,
            )
        window.append(now)
        return await call_next(request)
