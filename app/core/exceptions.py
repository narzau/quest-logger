# app/core/exceptions.py
from typing import Dict, Any, Optional, Type
from fastapi import HTTPException, status


class BusinessException(Exception):
    """Base exception for business rule violations."""

    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "business_error"

    def __init__(
        self, message: str, code: str = None, details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code or self.error_code
        self.details = details or {}
        super().__init__(self.message)

    def to_http_exception(self) -> HTTPException:
        """Convert this exception to an HTTPException"""
        return HTTPException(
            status_code=self.status_code,
            detail={
                "error": self.code,
                "message": self.message,
                **({"details": self.details} if self.details else {}),
            },
        )


# Resource-related exceptions
class ResourceNotFoundException(BusinessException):
    """Exception raised when a requested resource is not found."""

    status_code = status.HTTP_404_NOT_FOUND
    error_code = "resource_not_found"


class DuplicateResourceException(BusinessException):
    """Exception raised when attempting to create a duplicate resource."""

    status_code = status.HTTP_409_CONFLICT
    error_code = "resource_already_exists"


class ValidationException(BusinessException):
    """Exception raised when input validation fails."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "validation_error"


class ProcessingException(BusinessException):
    """Exception raised when processing or interpreting data fails."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "processing_error"


# Authentication and Authorization exceptions
class AuthenticationException(BusinessException):
    """Exception raised for authentication failures."""

    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "authentication_error"


class AuthorizationException(BusinessException):
    """Exception raised for authorization failures."""

    status_code = status.HTTP_403_FORBIDDEN
    error_code = "authorization_error"


# External Service exceptions
class ExternalServiceException(BusinessException):
    """Exception raised when an external service call fails."""

    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "external_service_error"


class ServiceTimeoutException(BusinessException):
    """Exception raised when an external service times out."""

    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    error_code = "service_timeout"


class RateLimitException(BusinessException):
    """Exception raised when rate limits are hit."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "rate_limit_exceeded"


# Feature/Subscription exceptions
class FeatureNotAvailableException(BusinessException):
    """Exception raised when a feature is not available for the user's plan."""

    status_code = status.HTTP_402_PAYMENT_REQUIRED
    error_code = "feature_not_available"


class PaymentRequiredException(BusinessException):
    """Exception raised when payment is required to access a feature."""

    status_code = status.HTTP_402_PAYMENT_REQUIRED
    error_code = "payment_required"


class QuotaExceededException(BusinessException):
    """Exception raised when a user's quota is exceeded."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "quota_exceeded"


# Map exception classes to HTTP status codes
EXCEPTION_STATUS_CODES: Dict[Type[BusinessException], int] = {
    ResourceNotFoundException: status.HTTP_404_NOT_FOUND,
    DuplicateResourceException: status.HTTP_409_CONFLICT,
    ValidationException: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ProcessingException: status.HTTP_422_UNPROCESSABLE_ENTITY,
    AuthenticationException: status.HTTP_401_UNAUTHORIZED,
    AuthorizationException: status.HTTP_403_FORBIDDEN,
    ExternalServiceException: status.HTTP_502_BAD_GATEWAY,
    ServiceTimeoutException: status.HTTP_504_GATEWAY_TIMEOUT,
    RateLimitException: status.HTTP_429_TOO_MANY_REQUESTS,
    FeatureNotAvailableException: status.HTTP_402_PAYMENT_REQUIRED,
    PaymentRequiredException: status.HTTP_402_PAYMENT_REQUIRED,
    QuotaExceededException: status.HTTP_429_TOO_MANY_REQUESTS,
    BusinessException: status.HTTP_400_BAD_REQUEST,
}
