import logging
from typing import Union, Dict, Any, Callable

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.core.exceptions import BusinessException

# Set up module logger
logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register custom exception handlers for the FastAPI application.

    Args:
        app: The FastAPI application instance
    """

    # Handle business exceptions
    @app.exception_handler(BusinessException)
    async def business_exception_handler(
        request: Request, exc: BusinessException
    ) -> JSONResponse:
        """
        Handle custom business exceptions.
        Converts them to a standardized JSON response.
        """
        logger.warning(
            f"Business exception: {exc.code}: {exc.message}",
            extra={
                "path": request.url.path,
                "method": request.method,
                "client_host": request.client.host if request.client else "unknown",
                "details": exc.details,
            },
        )

        content = {
            "error": exc.code,
            "message": exc.message,
        }

        # Add details if available
        if exc.details:
            content["details"] = exc.details

        return JSONResponse(status_code=exc.status_code, content=content)

    # Handle validation errors
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """
        Handle Pydantic validation errors.
        Formats them in a more user-friendly way.
        """
        # Extract validation errors in a simpler format
        simplified_errors: Dict[str, str] = {}

        for error in exc.errors():
            loc = error.get("loc", [])
            # Skip the first element if it's the body
            if loc and loc[0] in ("body", "query", "path"):
                loc = loc[1:]

            # Construct the field path
            field = ".".join(str(x) for x in loc)
            # Get the error message
            msg = error.get("msg", "Validation error")
            simplified_errors[field] = msg

        logger.warning(
            f"Validation error: {simplified_errors}",
            extra={
                "path": request.url.path,
                "method": request.method,
                "client_host": request.client.host if request.client else "unknown",
            },
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "validation_error",
                "message": "Input validation failed",
                "details": simplified_errors,
            },
        )

    # Handle internal server errors
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """
        Handle unhandled exceptions.
        Logs them as errors and returns a generic error message.
        """
        logger.error(
            f"Unhandled exception: {str(exc)}",
            exc_info=True,
            extra={
                "path": request.url.path,
                "method": request.method,
                "client_host": request.client.host if request.client else "unknown",
            },
        )

        # Don't expose details in production
        from app.core.config import settings

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_server_error",
                "message": str(exc)
                if settings.ENVIRONMENT != "production"
                else "An internal server error occurred",
            },
        )
