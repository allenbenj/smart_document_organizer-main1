"""Production dependency-injection container.

Type-keys are canonical. String-key access is supported only as a
compatibility bridge via aliases and emits deprecation warnings.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections import defaultdict
from typing import Any, Callable, Dict, Iterable, Optional, Type, TypeVar, Union

logger = logging.getLogger(__name__)

Key = Union[Type[Any], str]
T = TypeVar("T")


class ProductionServiceContainer:
    """Async DI container with singleton/factory support and parent fallback."""

    def __init__(self, parent: Optional["ProductionServiceContainer"] = None):
        self._parent = parent
        self._instances: Dict[Type[Any], Any] = {}
        self._factories: Dict[Type[Any], Callable[..., Any]] = {}
        self._singletons: Dict[Type[Any], bool] = {}
        self._dependencies: Dict[Type[Any], list[Key]] = {}
        self._aliases: Dict[str, Type[Any]] = {}
        self._singleton_locks: defaultdict[Type[Any], asyncio.Lock] = defaultdict(
            asyncio.Lock
        )
        self._warned_aliases: set[str] = set()
        logger.info("ProductionServiceContainer initialized")

    def _name(self, key: Key) -> str:
        return key.__name__ if hasattr(key, "__name__") else str(key)

    def _resolve_key(self, key: Key) -> Key:
        if isinstance(key, str) and key in self._aliases:
            if key not in self._warned_aliases:
                logger.warning(
                    "Deprecated string-key service lookup '%s'; use type-key '%s'",
                    key,
                    self._name(self._aliases[key]),
                )
                self._warned_aliases.add(key)
            return self._aliases[key]
        return key

    def register_alias(self, alias: str, target: Type[Any]) -> None:
        """Register a deprecated string alias that resolves to a type key."""
        self._aliases[alias] = target

    async def register_service(
        self,
        interface: Type[T],
        implementation: Callable[..., Any],
        singleton: bool = False,
        dependencies: Optional[Iterable[Key]] = None,
        aliases: Optional[Iterable[str]] = None,
    ) -> None:
        """Register a factory/service constructor for a type key."""
        self._factories[interface] = implementation
        self._singletons[interface] = singleton
        self._dependencies[interface] = list(dependencies or [])
        for alias in aliases or []:
            self.register_alias(alias, interface)
        logger.debug("Registered service: %s", self._name(interface))

    async def register_instance(
        self,
        interface: Type[T],
        instance: T,
        aliases: Optional[Iterable[str]] = None,
    ) -> None:
        """Register a concrete instance for a type key."""
        self._instances[interface] = instance
        self._singletons[interface] = True
        for alias in aliases or []:
            self.register_alias(alias, interface)
        logger.debug("Registered instance: %s", self._name(interface))

    async def get_service(self, interface: Key) -> Any:
        """Resolve a dependency by type key (or temporary string alias)."""
        resolved = self._resolve_key(interface)

        if not isinstance(resolved, type):
            if self._parent:
                return await self._parent.get_service(interface)
            raise ValueError(f"Service not registered: {self._name(interface)}")

        if resolved in self._instances:
            return self._instances[resolved]

        if resolved not in self._factories:
            if self._parent:
                return await self._parent.get_service(interface)
            raise ValueError(f"Service not registered: {self._name(resolved)}")

        if self._singletons.get(resolved, False):
            lock = self._singleton_locks[resolved]
            async with lock:
                if resolved in self._instances:
                    return self._instances[resolved]
                instance = await self._build_service(resolved)
                self._instances[resolved] = instance
                return instance

        return await self._build_service(resolved)

    async def _build_service(self, interface: Type[Any]) -> Any:
        deps: list[Any] = []
        for dep in self._dependencies.get(interface, []):
            deps.append(await self.get_service(dep))

        factory = self._factories[interface]
        out = factory(*deps)
        if inspect.isawaitable(out):
            return await out
        return out

    async def has_service(self, interface: Key) -> bool:
        resolved = self._resolve_key(interface)
        if isinstance(resolved, type):
            return (
                resolved in self._instances
                or resolved in self._factories
                or (self._parent is not None and await self._parent.has_service(interface))
            )
        return self._parent is not None and await self._parent.has_service(interface)

    def register_singleton(self, interface: Type[T], value: Union[T, Callable[[], T]]) -> None:
        """Sync compatibility helper used by legacy modules.

        If ``value`` is callable, it's treated as a singleton factory.
        Otherwise it's registered as an instance.
        """
        if callable(value):
            self._factories[interface] = value  # type: ignore[assignment]
            self._singletons[interface] = True
            self._dependencies[interface] = []
        else:
            self._instances[interface] = value
            self._singletons[interface] = True

    async def shutdown(self) -> None:
        """Shutdown all managed instances that expose async/sync close methods."""
        for instance in list(self._instances.values()):
            try:
                if hasattr(instance, "shutdown"):
                    result = instance.shutdown()
                    if inspect.isawaitable(result):
                        await result
                elif hasattr(instance, "close"):
                    result = instance.close()
                    if inspect.isawaitable(result):
                        await result
            except Exception as e:
                logger.error(
                    "Error shutting down service %s: %s",
                    instance.__class__.__name__,
                    e,
                )

        logger.info("ProductionServiceContainer shutdown complete")
