from functools import lru_cache
from typing import Any, Callable, Dict, Type, TypeVar, cast

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db

# Type variable for service classes
T = TypeVar("T")

# Global registry of service factories
_service_registry: Dict[Type[Any], Callable[..., Any]] = {}


def register_service(service_class: Type[T], factory: Callable[..., T]) -> None:
    """
    Register a service factory function.

    Args:
        service_class: The class of the service
        factory: Function that creates an instance of the service
    """
    _service_registry[service_class] = factory


def get_service(service_class: Type[T]) -> Callable[..., T]:
    """
    Get a dependency provider for a service.

    This function returns a dependency that will provide an instance of the
    requested service. The service must have been registered with register_service.

    If the service is not registered yet, we'll register it with a default factory
    that simply creates an instance with the database session.

    Args:
        service_class: The class of the service to provide

    Returns:
        A FastAPI dependency that provides the service

    Raises:
        KeyError: If the service class is not registered
    """
    # If service not registered, register it with a default factory
    if service_class not in _service_registry:
        # Default factory that just creates a new instance with db
        default_factory = lambda db: service_class(db)
        register_service(service_class, default_factory)

    factory = _service_registry[service_class]

    # Return a dependency function that will create the service
    async def _get_service(request: Request, db: Session = Depends(get_db)) -> T:
        # Check if service is already in request state
        service_key = f"service:{service_class.__name__}"
        if hasattr(request.state, service_key):
            return cast(T, getattr(request.state, service_key))

        # Create new service instance
        service = factory(db)

        # Cache in request state
        setattr(request.state, service_key, service)

        return service

    return _get_service


# Cache frequently used services with LRU cache
def cached_service(service_class: Type[T], maxsize: int = 32) -> Callable[..., T]:
    """
    Create a cached dependency provider for a service.

    This is similar to get_service but caches the created service instances.
    Useful for stateless services that can be reused.

    If the service is not registered yet, we'll register it with a default factory
    that simply creates an instance with the database session.

    Args:
        service_class: The class of the service to provide
        maxsize: Maximum size of the LRU cache

    Returns:
        A FastAPI dependency that provides the cached service
    """
    # If service not registered, register it with a default factory
    if service_class not in _service_registry:
        # Default factory that just creates a new instance with db
        default_factory = lambda db: service_class(db)
        register_service(service_class, default_factory)

    factory = _service_registry.get(service_class)

    # Cache to store service instances
    service_cache = {}

    async def _service_dependency(request: Request, db: Session = Depends(get_db)) -> T:
        # Check if service is already in request state
        service_key = f"service:{service_class.__name__}"
        if hasattr(request.state, service_key):
            return cast(T, getattr(request.state, service_key))

        # Use DB connection ID as cache key
        db_id = str(id(db))

        # Get service from cache or create new one
        if db_id not in service_cache:
            # Keep cache size under control
            if len(service_cache) >= maxsize:
                # Remove oldest item (first key)
                if service_cache:
                    oldest_key = next(iter(service_cache))
                    del service_cache[oldest_key]

            # Create new service instance
            service_cache[db_id] = factory(db)

        # Get service from cache
        service = service_cache[db_id]

        # Store in request state
        setattr(request.state, service_key, service)

        return service

    return _service_dependency
