"""
Organization Tab Utilities

Shared helper methods for organization workflows.
"""

import os
import re
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def normalize_root_scope(path_str: str) -> str:
    """Normalize folder path for consistent API usage."""
    p = path_str.strip()
    if not p:
        return ""
    p = p.replace("\\", "/")
    return p

def validate_canonical_path(path_str: str) -> str:
    """
    Find the actual case-sensitive path on disk if it exists.
    Fixes Windows (case-insensitive) to WSL (case-sensitive) mismatches.
    """
    p = normalize_root_scope(path_str)
    if not p: return ""
    
    path = Path(p)
    if path.exists():
        # It's already correct or we are on Windows
        return p
        
    # Try to find actual casing by walking up
    parts = list(path.parts)
    if not parts: return p
    
    current = Path(parts[0])
    for part in parts[1:]:
        if not current.exists(): break
        
        # Look for a case-insensitive match in current directory
        try:
            matched = False
            for entry in os.listdir(current):
                if entry.lower() == part.lower():
                    current = current / entry
                    matched = True
                    break
            if not matched:
                current = current / part
        except Exception as e:
            logger.warning(
                f"Error during canonical path validation for part '{part}' in '{current}': {e}"
            )
            current = current / part
            
    return normalize_root_scope(str(current))

def get_scope_prefixes(path_str: str) -> list[str]:
    """Build equivalent scope prefixes for Windows/WSL path variants."""
    root = normalize_root_scope(path_str)
    if not root:
        return []
    prefixes = [root]

    # Windows drive path -> WSL equivalent (/mnt/<drive>/...)
    m = re.match(r"^([A-Za-z]):/(.*)$", root)
    if m:
        drive = m.group(1).lower()
        rest = m.group(2).lstrip("/")
        prefixes.append(f"/mnt/{drive}/{rest}")

    # WSL path -> Windows equivalent (<DRIVE>:/...)
    m2 = re.match(r"^/mnt/([A-Za-z])/(.*)$", root)
    if m2:
        drive = m2.group(1).upper()
        rest = m2.group(2).lstrip("/")
        prefixes.append(f"{drive}:/{rest}")

    seen = set()
    unique = []
    for p in prefixes:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique

def get_existing_runtime_roots(root: str) -> list[str]:
    """Return root path variants that exist in current runtime."""
    existing: list[str] = []
    for candidate in get_scope_prefixes(root):
        try:
            # First try to fix casing
            canonical = validate_canonical_path(candidate)
            p = Path(canonical)
            if p.exists() and p.is_dir():
                existing.append(canonical)
        except Exception as e:
            logger.warning(f"Error checking runtime root '{candidate}': {e}")
            continue
    return existing
