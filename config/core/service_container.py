"""
Service Container - Dependency Injection Container
===================================================

This module provides a simple service container for dependency injection.
"""

from typing import Any, Callable, Dict, Optional, TypeVar

T = TypeVar("T")


class ServiceContainer:
    """
    Simple dependency injection container.

    Provides service registration and retrieval with support for:
    - Singleton services
    - Factory functions
    - Lazy initialization
    """

    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._singletons: Dict[str, Any] = {}

    def register(self, name: str, service: Any) -> None:
        """Register a service instance.

        Args:
            name: Service identifier
            service: Service instance
        """
        self._services[name] = service

    def register_factory(self, name: str, factory: Callable) -> None:
        """Register a factory function for lazy instantiation.

        Args:
            name: Service identifier
            factory: Factory function that creates the service
        """
        self._factories[name] = factory

    def register_singleton(self, name: str, instance: Any) -> None:
        """Register a singleton instance.

        Args:
            name: Service identifier
            instance: Singleton instance
        """
        self._singletons[name] = instance

    def get(self, name: str) -> Optional[Any]:
        """Get a service by name.

        Args:
            name: Service identifier

        Returns:
            Service instance or None if not found
        """
        # Check singletons first
        if name in self._singletons:
            return self._singletons[name]

        # Check registered services
        if name in self._services:
            return self._services[name]

        # Check factories
        if name in self._factories:
            return self._factories[name]()

        return None

    def has(self, name: str) -> bool:
        """Check if a service is registered.

        Args:
            name: Service identifier

        Returns:
            True if service is registered
        """
        return (
            name in self._services
            or name in self._factories
            or name in self._singletons
        )

    def remove(self, name: str) -> bool:
        """Remove a service.

        Args:
            name: Service identifier

        Returns:
            True if service was removed
        """
        removed = False
        if name in self._services:
            del self._services[name]
            removed = True
        if name in self._factories:
            del self._factories[name]
            removed = True
        if name in self._singletons:
            del self._singletons[name]
            removed = True
        return removed

    def clear(self) -> None:
        """Clear all registered services."""
        self._services.clear()
        self._factories.clear()
        self._singletons.clear()


# Global container instance
_container: Optional[ServiceContainer] = None


def get_container() -> ServiceContainer:
    """Get the global service container instance.

    Returns:
        Global ServiceContainer instance
    """
    global _container
    if _container is None:
        _container = ServiceContainer()
    return _container


def reset_container() -> None:
    """Reset the global service container."""
    global _container
    _container = None


__all__ = [
    "ServiceContainer",
    "get_container",
    "reset_container",
]
