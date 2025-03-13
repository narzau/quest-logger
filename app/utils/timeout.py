import asyncio
import logging
import functools
from typing import Callable, TypeVar, Any, Optional
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.exceptions import ProcessingException

# Set up module logger
logger = logging.getLogger(__name__)

T = TypeVar("T")


async def with_timeout(
    coro: asyncio.coroutines, timeout: float, error_message: str = "Operation timed out"
) -> Any:
    """
    Execute a coroutine with a timeout.

    Args:
        coro: The coroutine to execute
        timeout: Timeout in seconds
        error_message: Custom error message for timeout

    Returns:
        The result of the coroutine

    Raises:
        ProcessingException: If the operation times out
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.error(f"Timeout error: {error_message} (limit: {timeout}s)")
        raise ProcessingException(f"{error_message}")


def with_timeout_decorator(
    timeout: Optional[float] = None, error_message: str = "Operation timed out"
):
    """
    Decorator to add timeout to async functions.

    Args:
        timeout: Timeout in seconds, defaults to settings.DEFAULT_TIMEOUT
        error_message: Custom error message for timeout

    Returns:
        Decorated function with timeout
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            nonlocal timeout
            if timeout is None:
                timeout = settings.DEFAULT_TIMEOUT

            return await with_timeout(
                func(*args, **kwargs), timeout=timeout, error_message=error_message
            )

        return wrapper

    return decorator


@asynccontextmanager
async def timeout_context(timeout: float, error_message: str = "Operation timed out"):
    """
    Context manager for timing out an operation.

    Usage:
        async with timeout_context(5.0, "API call timed out"):
            result = await some_slow_operation()

    Args:
        timeout: Timeout in seconds
        error_message: Custom error message for timeout

    Yields:
        None

    Raises:
        ProcessingException: If the operation times out
    """
    try:
        # Create a task to be canceled on timeout
        task = asyncio.current_task()

        # Create a timer to cancel the task
        timer_handle = asyncio.get_event_loop().call_later(timeout, task.cancel)

        try:
            yield
        except asyncio.CancelledError:
            logger.error(f"Timeout error: {error_message} (limit: {timeout}s)")
            raise ProcessingException(error_message)
        finally:
            # Remove the timer if operation completed normally
            timer_handle.cancel()
    except Exception as e:
        if isinstance(e, ProcessingException):
            raise
        logger.error(f"Error in timeout context: {str(e)}", exc_info=True)
        raise
