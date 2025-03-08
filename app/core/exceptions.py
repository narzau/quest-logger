# app/core/exceptions.py


class BusinessException(Exception):
    """Base exception for business rule violations."""

    def __init__(self, message: str, code: str = None):
        self.message = message
        self.code = code
        super().__init__(self.message)


# You can also define more specific exceptions
class ResourceNotFoundException(BusinessException):
    """Exception raised when a requested resource is not found."""

    pass


class DuplicateResourceException(BusinessException):
    """Exception raised when attempting to create a duplicate resource."""

    pass


class ValidationException(BusinessException):
    """Exception raised when input validation fails."""

    pass


class ProcessingException(BusinessException):
    """Exception raised when processing or interpreting data fails."""

    pass
