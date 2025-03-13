import logging
import time
import uuid
from typing import Callable, Dict, Optional

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

# Set up logger
logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds a unique request ID to each request.

    This allows for tracking requests through the system and correlating logs.
    The request ID is added to the request state and as a response header.
    """

    def __init__(
        self,
        app: ASGIApp,
        header_name: str = "X-Request-ID",
        environment_header: Optional[str] = "X-Environment",
    ):
        super().__init__(app)
        self.header_name = header_name
        self.environment_header = environment_header

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Generate or get request ID
        request_id = request.headers.get(self.header_name) or str(uuid.uuid4())

        # Add request ID to request state
        request.state.request_id = request_id

        # Add environment to request state if configured
        if self.environment_header:
            environment = request.headers.get(self.environment_header, "unknown")
            request.state.environment = environment

        # Process the request and log timing
        start_time = time.time()

        try:
            # Call the next middleware or route handler
            response = await call_next(request)

            # Add request ID to response headers
            response.headers[self.header_name] = request_id

            # Add environment to response headers if configured
            if self.environment_header and hasattr(request.state, "environment"):
                response.headers[self.environment_header] = request.state.environment

            # Log the request
            self._log_request(request, response, start_time)

            return response

        except Exception as exc:
            # Log the exception with request ID
            self._log_exception(request, exc, start_time)
            raise

    def _log_request(
        self, request: Request, response: Response, start_time: float
    ) -> None:
        """Log details about the request and response."""
        process_time = time.time() - start_time
        status_code = response.status_code
        url = (
            f"{request.url.path}?{request.query_params}"
            if request.query_params
            else request.url.path
        )

        log_dict = {
            "request_id": getattr(request.state, "request_id", "unknown"),
            "method": request.method,
            "url": url,
            "status_code": status_code,
            "process_time_ms": round(process_time * 1000, 2),
            "client_host": request.client.host if request.client else "unknown",
        }

        # Choose log level based on status code
        if status_code >= 500:
            logger.error(f"Request failed: {log_dict}")
        elif status_code >= 400:
            logger.warning(f"Request error: {log_dict}")
        else:
            logger.info(f"Request completed: {log_dict}")

    def _log_exception(
        self, request: Request, exc: Exception, start_time: float
    ) -> None:
        """Log unhandled exceptions."""
        process_time = time.time() - start_time
        url = (
            f"{request.url.path}?{request.query_params}"
            if request.query_params
            else request.url.path
        )

        log_dict = {
            "request_id": getattr(request.state, "request_id", "unknown"),
            "method": request.method,
            "url": url,
            "process_time_ms": round(process_time * 1000, 2),
            "client_host": request.client.host if request.client else "unknown",
            "exception": str(exc),
        }

        logger.error(f"Unhandled exception during request: {log_dict}", exc_info=True)


class LogContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds request information to log records.

    This middleware uses the contextvar-based logging filter to add
    request_id and other context to all log records created during request processing.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Get request ID from state (set by RequestIdMiddleware)
        request_id = getattr(request.state, "request_id", "unknown")

        # Set logging context for this request
        log_context = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "client_host": request.client.host if request.client else "unknown",
        }

        # Use the existing FilteringAdapter or create one
        # This is a bit of a hack but allows us to not modify the logging setup
        from app.core.logging import request_context

        # Set the context for this request
        token = request_context.set(log_context)

        try:
            # Process the request
            response = await call_next(request)
            return response
        finally:
            # Clear the context when done
            request_context.reset(token)


def register_middlewares(app: FastAPI) -> None:
    """
    Register all middlewares with the FastAPI app.

    Note: Middleware is executed in reverse order of registration
    (last registered is executed first).

    Args:
        app: The FastAPI application instance
    """
    # Register RequestIdMiddleware (executed second)
    app.add_middleware(
        RequestIdMiddleware,
        header_name="X-Request-ID",
        environment_header="X-Environment",
    )

    # Register LogContextMiddleware (executed first)
    app.add_middleware(LogContextMiddleware)
