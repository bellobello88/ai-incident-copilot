import time

from prometheus_client import Counter, Histogram, make_asgi_app
from starlette.middleware.base import BaseHTTPMiddleware


HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["service", "method", "path", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["service", "method", "path"],
)

HTTP_REQUEST_ERRORS_TOTAL = Counter(
    "http_request_errors_total",
    "Total number of HTTP request errors",
    ["service", "method", "path"],
)


class MetricsMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, service_name: str):
        super().__init__(app)
        self.service_name = service_name

    async def dispatch(self, request, call_next):
        path = request.url.path

        if path == "/metrics":
            return await call_next(request)

        method = request.method
        start_time = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response

        except Exception:
            HTTP_REQUEST_ERRORS_TOTAL.labels(
                service=self.service_name,
                method=method,
                path=path,
            ).inc()
            raise

        finally:
            duration = time.perf_counter() - start_time

            HTTP_REQUESTS_TOTAL.labels(
                service=self.service_name,
                method=method,
                path=path,
                status_code=str(status_code),
            ).inc()

            HTTP_REQUEST_DURATION_SECONDS.labels(
                service=self.service_name,
                method=method,
                path=path,
            ).observe(duration)


def setup_metrics(app, service_name: str):
    app.add_middleware(MetricsMiddleware, service_name=service_name)
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)
