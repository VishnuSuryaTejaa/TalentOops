"""Structured logging configuration for TalentOps.

This module provides structured, JSON-formatted logging for production environments
with support for different log levels, formatting, and metrics collection.

Features:
- Structured JSON logging for compliance and monitoring
- Request/response time tracking
- Error tracking and alerting
- Contextual logging with request IDs
- Metrics collection (metrics module)
- Support for structured data in logs
"""
import logging
import sys
import json
import uuid
from collections import deque
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Optional
from contextvars import ContextVar

from fastapi import Request, Response
from fastapi.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings


# Request ID context variable for request tracing
request_id_context: ContextVar[str] = ContextVar("request_id", default="")


class JsonFormatter(logging.Formatter):
    """JSON-formatted log handler for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add additional context
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "extra_data"):
            log_data["extra_data"] = record.extra_data

        # Add exception information if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add stack trace if present
        if record.stack_info:
            log_data["stack_trace"] = self.formatStack(record.stack_info)

        return json.dumps(log_data)


class MetricsCollector:
    """Collects and tracks application metrics."""

    def __init__(self):
        """Initialize metrics collector."""
        self._request_counts: dict[str, int] = {}
        self._response_times: deque[float] = deque(maxlen=10_000)
        self._error_counts: dict[str, int] = {}
        self._service_calls: dict[str, int] = {}

    def increment_request_count(self, endpoint: str, status_code: int = 200):
        """Increment request count for an endpoint."""
        key = f"{endpoint}:{status_code}"
        self._request_counts[key] = self._request_counts.get(key, 0) + 1

    def record_response_time(self, response_time_ms: float):
        """Record response time in milliseconds."""
        self._response_times.append(response_time_ms)

    def increment_error_count(self, service: str, error_type: str):
        """Increment error count for a service and error type."""
        key = f"{service}:{error_type}"
        self._error_counts[key] = self._error_counts.get(key, 0) + 1

    def increment_service_call(self, service: str):
        """Increment service call count."""
        self._service_calls[service] = self._service_calls.get(service, 0) + 1

    def get_metrics(self) -> dict[str, Any]:
        """Get all collected metrics."""
        return {
            "request_counts": self._request_counts.copy(),
            "response_times_avg": sum(self._response_times) / len(self._response_times) if self._response_times else 0,
            "response_times_count": len(self._response_times),
            "error_counts": self._error_counts.copy(),
            "service_calls": self._service_calls.copy(),
        }

    def reset(self):
        """Reset all metrics."""
        self._request_counts.clear()
        self._response_times.clear()
        self._error_counts.clear()
        self._service_calls.clear()


# Global metrics collector
metrics_collector = MetricsCollector()


def get_metrics() -> MetricsCollector:
    """Get the global metrics collector instance."""
    return metrics_collector


def set_request_id(request_id: str):
    """Set request ID in context."""
    request_id_context.set(request_id)


def get_request_id() -> str:
    """Get current request ID from context."""
    return request_id_context.get("")


def log_method(name: str):
    """Decorator to add logging to methods.

    Usage:
        @log_method("data_service")
        async def fetch_data(self):
            # Method implementation
            pass
    """
    def decorator(method: Callable) -> Callable:
        @wraps(method)
        async def wrapper(*args, **kwargs):
            # Get instance if first arg is self
            instance = args[0] if args else None
            service_name = getattr(instance, "__class__.__name__", name) if instance else name

            # Log method entry
            logger = get_logger(service_name)
            request_id = get_request_id()
            extra_data = {"request_id": request_id} if request_id else {}

            logger.info(
                f"Method entry: {method.__name__}",
                extra={"extra_data": extra_data, "service": service_name}
            )

            # Update metrics
            metrics_collector.increment_service_call(service_name)

            # Call method
            try:
                result = await method(*args, **kwargs)
                logger.info(
                    f"Method completed: {method.__name__}",
                    extra={"extra_data": extra_data, "service": service_name}
                )
                return result
            except Exception as e:
                logger.error(
                    f"Method failed: {method.__name__}",
                    exc_info=True,
                    extra={"extra_data": extra_data, "service": service_name}
                )
                raise
        return wrapper
    return decorator


def log_async_function(name: str):
    """Decorator to add logging to async functions.

    Usage:
        @log_async_function("api_endpoint")
        async def process_request(request: Request):
            # Function implementation
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            logger = get_logger(name)
            request_id = get_request_id()
            extra_data = {"request_id": request_id} if request_id else {}

            logger.info(
                f"Function entry: {func.__name__}",
                extra={"extra_data": extra_data, "function": name}
            )

            try:
                result = await func(*args, **kwargs)
                logger.info(
                    f"Function completed: {func.__name__}",
                    extra={"extra_data": extra_data, "function": name}
                )
                return result
            except Exception as e:
                logger.error(
                    f"Function failed: {func.__name__}",
                    exc_info=True,
                    extra={"extra_data": extra_data, "function": name}
                )
                raise
        return wrapper
    return decorator


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses."""

    def __init__(self, app, **kwargs):
        """Initialize request logging middleware."""
        super().__init__(app, **kwargs)
        self.logger = get_logger(__name__)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log details."""
        # Generate request ID if not exists
        request_id = str(uuid.uuid4())[:8]
        set_request_id(request_id)

        # Extract client IP
        client_ip = request.client.host if request.client else "unknown"

        # Log request
        self.logger.info(
            "Request received",
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "client_ip": client_ip,
                "path": request.url.path,
            }
        )

        # Record start time
        start_time = datetime.now()

        try:
            # Process request
            response = await call_next(request)

            # Calculate response time
            end_time = datetime.now()
            response_time_ms = (end_time - start_time).total_seconds() * 1000

            # Log response
            self.logger.info(
                "Request completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "url": str(request.url),
                    "status_code": response.status_code,
                    "response_time_ms": round(response_time_ms, 2),
                    "client_ip": client_ip,
                }
            )

            # Update metrics
            metrics_collector.increment_request_count(
                request.url.path,
                response.status_code
            )
            metrics_collector.record_response_time(response_time_ms)

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Log error
            self.logger.error(
                "Request failed",
                exc_info=True,
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "url": str(request.url),
                    "error_type": type(e).__name__,
                    "client_ip": client_ip,
                }
            )

            # Update error metrics
            metrics_collector.increment_error_count(request.url.path, type(e).__name__)

            # Re-raise exception
            raise


class ErrorLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for capturing and logging errors."""

    def __init__(self, app, **kwargs):
        """Initialize error logging middleware."""
        super().__init__(app, **kwargs)
        self.logger = get_logger(__name__)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log any errors."""
        try:
            return await call_next(request)
        except Exception as e:
            # Log error with full details
            self.logger.error(
                "Unhandled error in request",
                exc_info=True,
                extra={
                    "request_id": get_request_id(),
                    "method": request.method,
                    "url": str(request.url),
                    "path": request.url.path,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                }
            )
            raise


def configure_logging():
    """Configure application logging.

    Sets up logging with structured JSON format and appropriate handlers.
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Create file handler
    file_handler = logging.FileHandler("talentops.log")
    file_handler.setLevel(log_level)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Create formatters
    json_formatter = JsonFormatter()
    console_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Set formatters
    file_handler.setFormatter(json_formatter)
    console_handler.setFormatter(console_formatter)

    # Add handlers to root logger
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Get logger for TalentOps
    logger = get_logger("TalentOps")

    logger.info(
        "Logging configured",
        extra={
            "log_level": log_level,
            "environment": "production" if settings.IS_PRODUCTION else "development",
            "version": "1.0.0",
        }
    )

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the specified name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)