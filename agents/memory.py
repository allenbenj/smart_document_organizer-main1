"""Memory mixin shim.

Use `MemoryMixin` for the generic storage behavior.
Use `LegalMemoryMixin` from `agents.base.agent_mixins` for legal-domain helpers.
"""

from mem_db.memory.memory_mixin import MemoryMixin  # noqa: F401

__all__ = ["MemoryMixin"]
