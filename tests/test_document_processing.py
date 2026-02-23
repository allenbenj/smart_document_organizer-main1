from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from agents.processors.document_processor import (
    DocumentProcessingConfig,
    DocumentProcessor,
)
from core.container.service_container_impl import ProductionServiceContainer


def _workspace_root() -> Path:
    root = os.getenv("WORKSPACE_ROOT", "").strip()
    if root:
        return Path(root).resolve()
    return Path(__file__).resolve().parents[1]


def _find_first(root: Path, patterns: list[str]) -> Path | None:
    for pattern in patterns:
        for hit in root.rglob(pattern):
            if hit.is_file():
                return hit
    return None


def _resolve_text_file(root: Path) -> Path:
    env = os.getenv("TEST_DOCUMENT_TEXT", "").strip()
    if env:
        path = Path(env).resolve()
        if path.exists():
            return path
    candidate = _find_first(root, ["*.txt", "*.md"])
    if candidate is None:
        pytest.skip("No text fixture found. Set TEST_DOCUMENT_TEXT or add a text file.")
    return candidate


def _resolve_pdf_file(root: Path) -> Path:
    env = os.getenv("TEST_DOCUMENT_PDF", "").strip()
    if env:
        path = Path(env).resolve()
        if path.exists():
            return path
    candidate = _find_first(root, ["*.pdf"])
    if candidate is None:
        pytest.skip("No PDF fixture found. Set TEST_DOCUMENT_PDF or add a PDF file.")
    return candidate


def _resolve_image_file(root: Path) -> Path:
    env = os.getenv("TEST_DOCUMENT_IMAGE", "").strip()
    if env:
        path = Path(env).resolve()
        if path.exists():
            return path
    candidate = _find_first(root, ["*.png", "*.jpg", "*.jpeg", "*.tif", "*.tiff"])
    if candidate is None:
        pytest.skip("No image fixture found. Set TEST_DOCUMENT_IMAGE or add an image file.")
    return candidate


@pytest.fixture
def processor() -> DocumentProcessor:
    container = ProductionServiceContainer()
    config = DocumentProcessingConfig(enable_ocr=True)
    return DocumentProcessor(services=container, config=config)


def test_extract_text_content(processor: DocumentProcessor) -> None:
    root = _workspace_root()
    text_file = _resolve_text_file(root)
    task_data = {
        "file_path": str(text_file),
        "options": {"extract_text": True},
    }
    result = asyncio.run(processor._process_task(task_data, {}))

    assert result["success"] is True
    doc = result["processed_document"]
    assert len((doc.get("content") or "").strip()) > 0


def test_metadata_extraction(processor: DocumentProcessor) -> None:
    root = _workspace_root()
    pdf_file = _resolve_pdf_file(root)
    task_data = {
        "file_path": str(pdf_file),
        "options": {"extract_metadata": True},
    }
    result = asyncio.run(processor._process_task(task_data, {}))

    assert result["success"] is True
    doc = result["processed_document"]
    assert "metadata" in doc
    assert doc["metadata"] is not None


def test_ocr_enabled_vs_disabled(processor: DocumentProcessor) -> None:
    root = _workspace_root()
    image_file = _resolve_image_file(root)
    task_data_on = {
        "file_path": str(image_file),
        "options": {"enable_ocr": True},
    }
    result_on = asyncio.run(processor._process_task(task_data_on, {}))
    assert result_on["success"] is True

    task_data_off = {
        "file_path": str(image_file),
        "options": {"enable_ocr": False},
    }
    result_off = asyncio.run(processor._process_task(task_data_off, {}))
    assert result_off["success"] is True
    doc_off = result_off["processed_document"]
    assert doc_off["processing_method"] == "ocr_disabled"
    assert doc_off["content"] == ""
    assert doc_off["metadata"].get("ocr_skipped") is True
