"""
Optimized caching system for legal document analysis.

This module provides intelligent caching strategies specifically designed
for legal document analysis workloads with TTL, LRU, and semantic caching.
"""

import asyncio
import hashlib  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
import time  # noqa: E402
from abc import ABC, abstractmethod  # noqa: E402
from collections import OrderedDict  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from enum import Enum  # noqa: E402
from typing import Any, Dict, Optional  # noqa: E402


class CacheStrategy(Enum):
    """Available caching strategies."""

    LRU = "lru"
    TTL = "ttl"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


@dataclass
class CacheEntry:
    """Cache entry with metadata."""

    value: Any
    created_at: float
    last_accessed: float
    access_count: int = 0
    ttl: Optional[float] = None

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl

    def touch(self):
        """Update access metadata."""
        self.last_accessed = time.time()
        self.access_count += 1


class CacheBackend(ABC):
    """Abstract cache backend interface."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set value in cache."""

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cache entries."""

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""


class MemoryCacheBackend(CacheBackend):
    """High-performance in-memory cache backend."""

    def __init__(self, max_size: int = 1000, default_ttl: Optional[float] = None):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self._lock = asyncio.Lock()

        self.logger = logging.getLogger(__name__)

    async def get(self, key: str) -> Optional[Any]:
        """Get value with LRU tracking."""
        async with self._lock:
            if key not in self.cache:
                self.misses += 1
                return None

            entry = self.cache[key]

            # Check expiration
            if entry.is_expired():
                del self.cache[key]
                self.misses += 1
                return None

            # Update access and move to end (most recent)
            entry.touch()
            self.cache.move_to_end(key)
            self.hits += 1

            return entry.value

    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set value with eviction policy."""
        async with self._lock:
            # Use provided TTL or default
            entry_ttl = ttl or self.default_ttl

            # Create cache entry
            entry = CacheEntry(
                value=value,
                created_at=time.time(),
                last_accessed=time.time(),
                ttl=entry_ttl,
            )

            # Add/update entry
            if key in self.cache:
                del self.cache[key]  # Remove old entry

            self.cache[key] = entry
            self.cache.move_to_end(key)  # Mark as most recent

            # Evict if over capacity
            while len(self.cache) > self.max_size:
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                self.evictions += 1

    async def delete(self, key: str) -> bool:
        """Delete specific key."""
        async with self._lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False

    async def clear(self) -> None:
        """Clear all entries."""
        async with self._lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0
            self.evictions = 0

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0.0

        return {
            "backend_type": "memory",
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "evictions": self.evictions,
            "memory_usage_estimate": self._estimate_memory_usage(),
        }

    def _estimate_memory_usage(self) -> int:
        """Estimate memory usage in bytes."""
        # Rough estimation based on entry count
        # In production, could use more sophisticated memory tracking
        return len(self.cache) * 1024  # Assume ~1KB per entry


class SemanticCacheBackend(MemoryCacheBackend):
    """Semantic cache that matches similar content."""

    def __init__(self, max_size: int = 1000, similarity_threshold: float = 0.8):
        super().__init__(max_size)
        self.similarity_threshold = similarity_threshold
        self.semantic_index: Dict[str, str] = {}  # hash -> semantic_key

    async def get(self, key: str) -> Optional[Any]:
        """Get with semantic matching."""
        # Try exact match first
        result = await super().get(key)
        if result is not None:
            return result

        # Try semantic matching
        semantic_key = self._generate_semantic_key(key)
        if semantic_key in self.semantic_index:
            actual_key = self.semantic_index[semantic_key]
            return await super().get(actual_key)

        return None

    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set with semantic indexing."""
        await super().set(key, value, ttl)

        # Add to semantic index
        semantic_key = self._generate_semantic_key(key)
        self.semantic_index[semantic_key] = key

    def _generate_semantic_key(self, key: str) -> str:
        """Generate semantic key for similar content matching."""
        # For document analysis, could use content hashing or embedding similarity
        # This is a simplified version using normalized content hash

        try:
            # Try to parse as JSON to extract content
            data = json.loads(key)
            content = data.get("content_hash", key)
        except (json.JSONDecodeError, AttributeError):
            content = key

        # Create normalized hash
        normalized = content.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()[:16]


class LegalCache:
    """
    High-performance caching system optimized for legal document analysis.

    Features:
    - Multiple caching strategies (LRU, TTL, Semantic)
    - Async-safe operations
    - Comprehensive statistics
    - Configurable eviction policies
    """

    def __init__(
        self,
        strategy: CacheStrategy = CacheStrategy.LRU,
        max_size: int = 1000,
        ttl_seconds: Optional[float] = None,
        similarity_threshold: float = 0.8,
    ):
        self.strategy = strategy
        self.logger = logging.getLogger(__name__)

        # Initialize appropriate backend
        if strategy == CacheStrategy.SEMANTIC:
            self.backend = SemanticCacheBackend(max_size, similarity_threshold)
        else:
            self.backend = MemoryCacheBackend(max_size, ttl_seconds)

        self.logger.info(f"Initialized LegalCache with {strategy.value} strategy")

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache with strategy-specific logic.
        """
        try:
            result = await self.backend.get(key)
            if result is not None:
                self.logger.debug(f"Cache hit for key: {key[:50]}...")
            else:
                self.logger.debug(f"Cache miss for key: {key[:50]}...")
            return result

        except Exception as e:
            self.logger.warning(f"Cache get error: {str(e)}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """
        Set value in cache with optional TTL.
        """
        try:
            await self.backend.set(key, value, ttl)
            self.logger.debug(f"Cache set for key: {key[:50]}...")

        except Exception as e:
            self.logger.warning(f"Cache set error: {str(e)}")

    async def delete(self, key: str) -> bool:
        """
        Delete specific key from cache.
        """
        try:
            result = await self.backend.delete(key)
            if result:
                self.logger.debug(f"Cache delete for key: {key[:50]}...")
            return result

        except Exception as e:
            self.logger.warning(f"Cache delete error: {str(e)}")
            return False

    async def clear(self) -> None:
        """
        Clear all cache entries.
        """
        try:
            await self.backend.clear()
            self.logger.info("Cache cleared")

        except Exception as e:
            self.logger.warning(f"Cache clear error: {str(e)}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive cache statistics.
        """
        stats = self.backend.get_stats()
        stats["strategy"] = self.strategy.value
        return stats

    def get_hit_rate(self) -> float:
        """
        Get current cache hit rate.
        """
        stats = self.get_stats()
        return stats.get("hit_rate", 0.0)

    async def warm_up(self, key_value_pairs: Dict[str, Any]) -> None:
        """
        Warm up cache with initial data.
        """
        self.logger.info(f"Warming up cache with {len(key_value_pairs)} entries")

        for key, value in key_value_pairs.items():
            await self.set(key, value)

    def create_cache_key(self, *args, **kwargs) -> str:
        """
        Create standardized cache key from arguments.
        """
        # Combine positional and keyword arguments
        key_data = {"args": args, "kwargs": sorted(kwargs.items())}

        # Create hash-based key
        key_json = json.dumps(key_data, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_json.encode()).hexdigest()

        return f"legal_cache_{key_hash}"


def cache_result(
    cache_instance: LegalCache,
    ttl: Optional[float] = None,
    key_func: Optional[callable] = None,
):
    """
    Decorator for caching function results.

    Args:
        cache_instance: LegalCache instance to use
        ttl: Time-to-live for cached results
        key_func: Function to generate cache key from args/kwargs
    """

    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = cache_instance.create_cache_key(
                    func.__name__, *args, **kwargs
                )

            # Try cache first
            cached_result = await cache_instance.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache_instance.set(cache_key, result, ttl)

            return result

        def sync_wrapper(*args, **kwargs):
            # For non-async functions, run in event loop
            async def async_exec():
                return await async_wrapper(*args, **kwargs)

            try:
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(async_exec())
            except RuntimeError:
                # No event loop running
                return asyncio.run(async_exec())

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
