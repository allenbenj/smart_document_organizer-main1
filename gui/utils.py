"""
Common utility functions for the GUI.
"""
from __future__ import annotations

import os
import logging
from typing import Any, Callable, Dict

logger = logging.getLogger(__name__)

def extract_content_from_response(resp: Dict[str, Any]) -> str:
    """Extract document content from process_document API response.
    
    Handles the actual API response structure:
    {"data": {"processed_document": {"content": "..."}}}
    """
    data = resp.get("data", {})
    if isinstance(data, dict):
        # Try current structure: data.processed_document.content
        if "processed_document" in data:
            proc_doc = data["processed_document"]
            if isinstance(proc_doc, dict):
                return proc_doc.get("content") or proc_doc.get("text") or ""
        
        # Fallback to legacy structures
        if "value" in data and isinstance(data["value"], dict):
            data = data["value"]
        return data.get("content") or data.get("text") or ""
    return ""


def read_text_file_if_supported(file_path: str) -> str:
    """Read raw text for plaintext-like files to avoid unnecessary transforms."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in {".txt", ".md", ".markdown", ".csv", ".json", ".log"}:
        return ""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except (IOError, UnicodeDecodeError) as e: # More specific exceptions for file reading
        logger.warning("Error reading file '%s': %s", file_path, e)
        return ""
    except Exception as e: # Catch any other unexpected errors
        logger.exception("Unexpected error reading file '%s': %s", file_path, e) # Log the unexpected error
        return ""


def collect_folder_content(
    folder_path: str,
    *,
    process_document_fn: Callable[[str], Dict[str, Any]],
    extract_fn: Callable[[Dict[str, Any]], str] = extract_content_from_response,
    is_interruption_requested_fn: Callable[[], bool] | None = None,
) -> str:
    """Collect and concatenate content from supported files in a folder."""
    if not folder_path or not os.path.isdir(folder_path):
        return ""
    supported_exts = {
        ".txt",
        ".md",
        ".pdf",
        ".docx",
        ".doc",
        ".rtf",
        ".json",
        ".csv",
        ".html",
        ".htm",
    }
    chunks: list[str] = []
    for root, _, files in os.walk(folder_path):
        for name in sorted(files):
            if is_interruption_requested_fn and is_interruption_requested_fn():
                return ""
            _, ext = os.path.splitext(name)
            if ext.lower() not in supported_exts:
                continue
            path = os.path.join(root, name)
            try:
                resp = process_document_fn(path)
                content = extract_fn(resp).strip()
                if content:
                    chunks.append(f"--- FILE: {path} ---\n{content}")
            except Exception as e:
                logger.warning("Error processing file '%s' in collect_folder_content: %s", path, e)
                continue
    return "\n\n".join(chunks)
