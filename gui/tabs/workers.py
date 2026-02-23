"""
Workers and Dialogs for GUI Tabs

This module contains worker threads and dialog classes used by the GUI tabs.
"""

import os
import time
import logging
import json # New import
from typing import Optional

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QDialog, QLabel, QTextEdit, QVBoxLayout

try:
    import requests
    import requests.exceptions # New import
except ImportError:
    requests = None  # type: ignore

from ..services import api_client
from ..core.path_config import resolve_local_model_path
from ..utils import (
    collect_folder_content,
    extract_content_from_response,
    read_text_file_if_supported,
)

logger = logging.getLogger(__name__)




def _read_text_file_if_supported(file_path: str) -> str:
    """Backwards-compatible wrapper over shared GUI utility."""
    return read_text_file_if_supported(file_path)


def _collect_folder_content_utility(folder_path: str, is_interruption_requested_fn=None) -> str:
    """Backwards-compatible wrapper over shared GUI utility."""
    return collect_folder_content(
        folder_path,
        process_document_fn=api_client.process_document,
        extract_fn=extract_content_from_response,
        is_interruption_requested_fn=is_interruption_requested_fn,
    )


class UploadFileWorker(QThread):
    finished_ok = Signal(dict)
    finished_err = Signal(str)

    def __init__(self, path: str):
        super().__init__()
        self.path = path

    def run(self):  # noqa: C901
        try:
            print(f"[UploadFileWorker] Processing {self.path}...")
            if self.isInterruptionRequested():
                return
            if not requests:
                raise RuntimeError("requests not available")
            result = api_client.process_document(self.path)
            print("[UploadFileWorker] Success.")
            self.finished_ok.emit(result)
        except Exception as e:
            print(f"[UploadFileWorker] Error: {e}")
            self.finished_err.emit(str(e))


class UploadFolderWorker(QThread):
    finished_ok = Signal(dict)
    finished_err = Signal(str)

    def __init__(self, path: str):
        super().__init__()
        self.path = path

    def run(self):  # noqa: C901
        try:
            print(f"[UploadFolderWorker] Processing folder {self.path}...")
            if self.isInterruptionRequested():
                return
            if not requests:
                raise RuntimeError("requests not available")
            
            # Use the exact folder selected by the user to keep behavior explicit.

            if not os.path.exists(self.path):
                raise FileNotFoundError(f"Folder not found: {self.path}")

            files = [f for f in os.listdir(self.path) if os.path.isfile(os.path.join(self.path, f))]
            print(f"[UploadFolderWorker] Found {len(files)} files in folder.")
            
            results = {"processed": [], "errors": []}
            for filename in files:
                if self.isInterruptionRequested():
                    break
                full_path = os.path.join(self.path, filename)
                print(f"[UploadFolderWorker] Uploading {filename}...")
                try:
                    res = api_client.process_document(full_path)
                    results["processed"].append(res)
                except Exception as e:
                    print(f"[UploadFolderWorker] Failed {filename}: {e}")
                    results["errors"].append(str(e))
            
            print(f"[UploadFolderWorker] Finished. Processed: {len(results['processed'])}, Errors: {len(results['errors'])}")
            self.finished_ok.emit(results)

        except Exception as e:
            print(f"[UploadFolderWorker] Error: {e}")
            self.finished_err.emit(str(e))
            # Collect all files in folder
            file_paths = []
            for root, _, filenames in os.walk(self.path):
                for filename in filenames:
                    filepath = os.path.join(root, filename)
                    file_paths.append(filepath)
            if not file_paths:
                raise RuntimeError("No files found in folder")
            result = api_client.process_documents_batch(file_paths)
            self.finished_ok.emit(result)
        except Exception as e:
            self.finished_err.emit(str(e))


class UploadManyFilesWorker(QThread):
    finished_ok = Signal(dict)
    finished_err = Signal(str)
    progress_update = Signal(int, str) # progress_pct, status_msg

    def __init__(self, paths: list[str], options: Optional[dict] = None, job_id: Optional[str] = None):
        super().__init__()
        self.paths = paths
        self.options = options or {}
        self.job_id = job_id

    def run(self):  # noqa: C901
        try:
            if self.isInterruptionRequested():
                return
            
            if not self.paths:
                raise RuntimeError("No files provided")
            
            # Emit progress update signal instead of direct service update
            self.progress_update.emit(10, "Starting batch upload...")
                
            result = api_client.process_documents_batch(self.paths, self.options)
            
            if self.isInterruptionRequested():
                return

            self.progress_update.emit(100, "Processing complete")
            self.finished_ok.emit(result)
        except Exception as e:
            self.finished_err.emit(str(e))


class KGImportFromTextWorker(QThread):
    finished_ok = Signal(dict)
    finished_err = Signal(str)

    def __init__(self, text: str):
        super().__init__()
        self.text = text

    def run(self):  # noqa: C901
        try:
            if self.isInterruptionRequested():
                return
            if not requests:
                raise RuntimeError("requests not available")
            result = api_client.import_text_to_knowledge(self.text)
            self.finished_ok.emit(result)
        except Exception as e:
            self.finished_err.emit(str(e))


class ProcessedDocDetailsDialog(QDialog):
    """Dialog for displaying processed document details."""

    def __init__(self, doc_data: dict, parent=None):
        super().__init__(parent)
        self.doc_data = doc_data
        self.setWindowTitle("Processed Document Details")
        self.setGeometry(200, 200, 600, 400)
        self.init_ui()

    def init_ui(self):
        """Initialize the dialog UI."""
        layout = QVBoxLayout()

        # Document info
        info_label = QLabel(f"Document: {self.doc_data.get('filename', 'Unknown')}")
        layout.addWidget(info_label)

        # Content preview
        content_label = QLabel("Content Preview:")
        layout.addWidget(content_label)

        self.content_text = QTextEdit()
        self.content_text.setPlainText(
            self.doc_data.get("processed_document", {}).get("content", "")
        )
        self.content_text.setReadOnly(True)
        layout.addWidget(self.content_text)

        # Metadata
        metadata_label = QLabel("Metadata:")
        layout.addWidget(metadata_label)

        self.metadata_text = QTextEdit()
        self.metadata_text.setPlainText(
            str(self.doc_data.get("processed_document", {}).get("metadata", {}))
        )
        self.metadata_text.setReadOnly(True)
        layout.addWidget(self.metadata_text)

        self.setLayout(layout)


class LegalReasoningDetailsDialog(QDialog):
    """Dialog for displaying legal reasoning details."""

    def __init__(self, reasoning_data: dict, parent=None):
        super().__init__(parent)
        self.reasoning_data = reasoning_data
        self.setWindowTitle("Legal Reasoning Details")
        self.setGeometry(200, 200, 600, 400)
        self.init_ui()

    def init_ui(self):
        """Initialize the dialog UI."""
        layout = QVBoxLayout()

        # Reasoning info
        info_label = QLabel(f"Case: {self.reasoning_data.get('case_name', 'Unknown')}")
        layout.addWidget(info_label)

        # Reasoning text
        reasoning_label = QLabel("Reasoning:")
        layout.addWidget(reasoning_label)

        self.reasoning_text = QTextEdit()
        self.reasoning_text.setPlainText(
            self.reasoning_data.get("reasoning", "")
        )
        self.reasoning_text.setReadOnly(True)
        layout.addWidget(self.reasoning_text)

        # Conclusion
        conclusion_label = QLabel("Conclusion:")
        layout.addWidget(conclusion_label)

        self.conclusion_text = QTextEdit()
        self.conclusion_text.setPlainText(
            self.reasoning_data.get("conclusion", "")
        )
        self.conclusion_text.setReadOnly(True)
        layout.addWidget(self.conclusion_text)

        self.setLayout(layout)


class SemanticAnalysisWorker(QThread):
    """Worker thread for semantic analysis operations."""

    result_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(
        self,
        asyncio_thread,
        file_path,
        text_input,
        analysis_type,
        folder_path: str = "",
        options: Optional[dict] = None,
    ):
        super().__init__()
        self.asyncio_thread = asyncio_thread
        self.file_path = file_path
        self.text_input = text_input
        self.analysis_type = analysis_type
        self.folder_path = folder_path
        self.options = options or {}

    def run(self):  # noqa: C901
        """Execute semantic analysis via API or local clustering engine."""
        try:
            logger.info(f"[SemanticInfoWorker] Starting '{self.analysis_type}' analysis...")
            if self.isInterruptionRequested():
                return
            
            # Determine text to analyze
            content = self.text_input.strip()
            if not content and self.file_path:
                logger.info(f"[SemanticInfoWorker] Reading content from {self.file_path}...")
                resp = api_client.process_document(self.file_path)
                content = extract_content_from_response(resp)
            
            if not content and self.folder_path:
                logger.info(f"[SemanticInfoWorker] Collecting content from folder: {self.folder_path}...")
                content = _collect_folder_content_utility(self.folder_path, self.isInterruptionRequested)
            
            if not content:
                raise RuntimeError("No content to analyze.")

            if self.isInterruptionRequested():
                return

            # OPTION 1: High-Resolution Strategic Clustering (Formal Service)
            if self.analysis_type == "Strategic Clustering":
                logger.info("[SemanticInfoWorker] Launching formal ThematicDiscoveryService...")
                try:
                    from services.thematic_discovery_service import ThematicDiscoveryService
                    import asyncio
                    
                    # Resolve manager and loop
                    manager = getattr(self.asyncio_thread, "agent_manager", None)
                    if manager is None:
                        try:
                            from agents.production_agent_manager import get_production_agent_manager
                            manager = get_production_agent_manager()
                        except Exception as exc:
                            logger.warning(
                                "SemanticInfoWorker could not initialize production agent manager: %s",
                                exc,
                            )

                    loop = getattr(self.asyncio_thread, "loop", None)
                    if not loop:
                        raise RuntimeError("Asyncio loop not available in worker")
                        
                    service = ThematicDiscoveryService(manager)
                    
                    # Run end-to-end audit via the asyncio loop
                    doc_id = os.path.basename(self.file_path) if self.file_path else "manual_input"
                    
                    # Bridge synchronous thread to async coroutine
                    future = asyncio.run_coroutine_threadsafe(
                        service.discover_strategic_themes(content, doc_id), 
                        loop
                    )
                    results = future.result(timeout=300) # 5 minute timeout for large files
                    
                    self.result_ready.emit({"type": "strategic_discovery", "data": results})
                    return
                except requests.exceptions.RequestException as e:
                    logger.error(f"[SemanticInfoWorker] ThematicDiscoveryService API connection error: {e}")
                    raise
                except json.JSONDecodeError as e:
                    logger.error(f"[SemanticInfoWorker] ThematicDiscoveryService invalid API response: {e}")
                    raise
                except Exception as e:
                    logger.exception(f"[SemanticInfoWorker] Discovery Service failed: {e}")
                    raise

            # OPTION 2: Standard Semantic Analysis (API or Local Long-Summarizer)
            if self.analysis_type == "Summarization" and len(content) > 5000:
                logger.info(f"[SemanticInfoWorker] Document length {len(content)} exceeds 5k chars. Using local LED-LongSummarizer...")
                try:
                    from transformers import pipeline as transformers_pipeline
                    led_ref = resolve_local_model_path(
                        env_var="SMART_DOC_LED_MODEL_PATH",
                        relative_path="models/led-base-16384",
                    )
                    summarizer = transformers_pipeline("summarization", model=led_ref, tokenizer=led_ref)
                    # Process in a single large window (LED specialty)
                    summary = summarizer(content[:16000], max_length=500, min_length=100, do_sample=False)[0]["summary_text"]
                    self.result_ready.emit({"summary": summary, "engine": "local_led_longformer"})
                    return
                except Exception as e: # This exception could be specific to transformers pipeline
                    logger.warning(f"[SemanticInfoWorker] Local LED failed, falling back to API: {e}")

            if not requests:
                raise RuntimeError("requests not available for API analysis")
            
            logger.info(f"[SemanticInfoWorker] Analyzing {len(content)} chars via API...")
            body = api_client.analyze_semantic(content, {
                "analysis_type": self.analysis_type,
                "options": self.options,
            })
            data = body.get("data") or body.get("details") or body
            self.result_ready.emit(data)
        except requests.exceptions.RequestException as e:
            self.error_occurred.emit(f"API connection error: {e}")
        except json.JSONDecodeError as e:
            self.error_occurred.emit(f"Invalid API response: {e}")
        except RuntimeError as e:
            self.error_occurred.emit(str(e))
        except Exception as e:
            self.error_occurred.emit(f"An unexpected error occurred: {e}")
    def _label_clusters_with_llm(self, clusters: dict) -> dict:
        """Use LLM to identify high-level themes for each cluster."""
        labeled_clusters = {}
        
        # We'll use the sync-wrapped API client for rapid labeling
        for cid, items in clusters.items():
            if not items: continue
            
            # Take representative sample (first 3 sentences)
            sample = "\n".join(items[:3])
            prompt = f"Identify a 3-5 word legal theme for these sentences:\n\n{sample}\n\nTheme:"
            
            try:
                # Targeted low-token call
                res = api_client.analyze_semantic(sample, {"analysis_type": "Key Phrases"})
                # Fallback heuristic if API is slow: use first few words
                theme = res.get("summary") or res.get("data", {}).get("summary") or f"Theme {int(cid)+1}"
                if len(theme) > 50: theme = theme[:47] + "..."
                labeled_clusters[theme] = items
            except Exception:
                labeled_clusters[f"Cluster {int(cid)+1}"] = items
                
        return labeled_clusters


class EntityExtractionWorker(QThread):
    """Worker thread for entity extraction operations."""

    result_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(
        self,
        asyncio_thread,
        file_path,
        text_input,
        extraction_type,
        options: Optional[dict] = None,
    ):
        super().__init__()
        self.asyncio_thread = asyncio_thread
        self.file_path = file_path
        self.text_input = text_input
        self.extraction_type = extraction_type
        self.options = options or {}

    def run(self):  # noqa: C901
        """Execute entity extraction via API."""
        try:
            logger.info("[EntityExtractionWorker] Starting extraction...")
            if self.isInterruptionRequested():
                return
            if not requests:
                raise RuntimeError("requests not available")
            # Determine text to extract from
            content = self.text_input.strip()
            if not content and self.file_path:
                logger.info(f"[EntityExtractionWorker] Reading content from file: {self.file_path}")
                # Prefer direct raw-text read for plaintext-like formats.
                content = _read_text_file_if_supported(self.file_path)
                if not content:
                    # Use document processor for binary formats (pdf/docx/etc.).
                    resp = api_client.process_document(self.file_path)
                    content = extract_content_from_response(resp)

            if not content:
                logger.info("[EntityExtractionWorker] No content found.")
                raise RuntimeError("No content to analyze")
            if self.isInterruptionRequested():
                return
            # Call entity extraction endpoint
            entity_types = self.options.get("entity_types")
            logger.info(f"[EntityExtractionWorker] Calling extract_entities (Types: {entity_types})...")
            if not entity_types and self.extraction_type and self.extraction_type != "All":
                entity_types = [self.extraction_type]

            requested_model = str(
                self.options.get("extraction_model", "auto") or "auto"
            ).strip().lower()
            model_plan = (
                [requested_model]
                if requested_model in {"auto", "gliner", "llm", "hf_ner", "spacy", "patterns"}
                else ["auto"]
            )
            if requested_model != "auto":
                # Usability hardening: never dead-end on one broken model path.
                model_plan.extend(["auto", "gliner", "patterns"])

            warnings: list[str] = []
            final_body: dict = {}
            final_entities: list = []
            final_relationships: list = []
            final_extraction_stats: dict = {}
            attempts: list[dict] = []

            for model_name in model_plan:
                if model_name in {a.get("model") for a in attempts}:
                    continue
                body = api_client.extract_entities(
                    content,
                    entity_types=entity_types,
                    extraction_type="ner",
                    extra_options={
                        "extraction_model": model_name,
                        "provenance_requested": True,
                    },
                )
                data = body.get("data") if isinstance(body.get("data"), dict) else {}
                entities = (
                    body.get("entities")
                    if isinstance(body.get("entities"), list)
                    else data.get("entities")
                )
                relationships = (
                    body.get("relationships")
                    if isinstance(body.get("relationships"), list)
                    else data.get("relationships")
                )
                extraction_stats = (
                    body.get("extraction_stats")
                    if isinstance(body.get("extraction_stats"), dict)
                    else data.get("extraction_stats")
                    if isinstance(data.get("extraction_stats"), dict)
                    else {}
                )
                methods_used = extraction_stats.get("extraction_methods_used", [])
                methods_set = (
                    {str(m).strip().lower() for m in methods_used}
                    if isinstance(methods_used, list)
                    else set()
                )
                attempts.append(
                    {
                        "model": model_name,
                        "success": bool(body.get("success", True)),
                        "entities": len(entities) if isinstance(entities, list) else 0,
                        "methods_used": sorted(methods_set),
                        "error": body.get("error"),
                    }
                )

                if not bool(body.get("success", True)):
                    warnings.append(
                        f"Model {model_name} failed: {body.get('error') or 'unknown'}"
                    )
                    continue

                if isinstance(entities, list) and entities:
                    final_body = body
                    final_entities = entities
                    final_relationships = (
                        relationships if isinstance(relationships, list) else []
                    )
                    final_extraction_stats = (
                        extraction_stats if isinstance(extraction_stats, dict) else {}
                    )
                    if model_name != requested_model:
                        warnings.append(
                            f"Fallback used: requested={requested_model}, used={model_name}"
                        )
                    break

                warnings.append(f"Model {model_name} returned zero entities.")

            if not final_body:
                # keep last attempt payload for diagnostics
                final_body = body if "body" in locals() else {}
                final_extraction_stats = (
                    extraction_stats if "extraction_stats" in locals() and isinstance(extraction_stats, dict) else {}
                )
                final_entities = []
                final_relationships = []

            if warnings or attempts:
                final_extraction_stats = dict(final_extraction_stats or {})
                final_extraction_stats["warnings"] = warnings
                final_extraction_stats["model_attempts"] = attempts

            self.result_ready.emit(
                {
                    "success": bool(final_body.get("success", True)),
                    "error": final_body.get("error"),
                    "source_text": content,
                    "entities": final_entities,
                    "relationships": final_relationships,
                    "extraction_stats": final_extraction_stats,
                    "raw_response": final_body,
                }
            )
        except (IOError, FileNotFoundError, PermissionError) as e:
            self.error_occurred.emit(f"File access error: {e}")
        except requests.exceptions.RequestException as e:
            self.error_occurred.emit(f"API connection error: {e}")
        except json.JSONDecodeError as e:
            self.error_occurred.emit(f"Invalid API response: {e}")
        except RuntimeError as e:
            self.error_occurred.emit(str(e))
        except Exception as e:
            self.error_occurred.emit(f"An unexpected error occurred: {e}")

class EntityExtractionFolderWorker(QThread):
    """Worker thread for folder-based entity extraction operations."""

    result_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, folder_path: str, extraction_type: str, options: Optional[dict] = None):
        super().__init__()
        self.folder_path = folder_path
        self.extraction_type = extraction_type
        self.options = options or {}

    def run(self):  # noqa: C901
        try:
            if self.isInterruptionRequested():
                return
            if not requests:
                raise RuntimeError("requests not available")
            if not self.folder_path or not os.path.isdir(self.folder_path):
                raise RuntimeError("Invalid folder path")

            supported_exts = {
                ".txt",
                ".md",
                ".markdown",
                ".pdf",
                ".docx",
                ".doc",
                ".rtf",
                ".json",
                ".csv",
                ".html",
                ".htm",
            }

            paths: list[str] = []
            for root, _, files in os.walk(self.folder_path):
                for name in sorted(files):
                    _, ext = os.path.splitext(name)
                    if ext.lower() in supported_exts:
                        paths.append(os.path.join(root, name))

            if not paths:
                raise RuntimeError("No supported files found in folder")

            entity_types = self.options.get("entity_types")
            if not entity_types and self.extraction_type and self.extraction_type != "All":
                entity_types = [self.extraction_type]

            all_entities: list[dict] = []
            all_relationships: list[dict] = []
            total_processed = 0
            file_chunks: list[str] = []
            file_errors: list[dict] = []
            methods_used: set[str] = set()
            requested_model = str(
                self.options.get("extraction_model", "auto") or "auto"
            ).strip().lower()
            # Rate limiting: throttle backend extraction calls for folder runs.
            # Default is conservative to avoid API saturation on large folders.
            requests_per_second = float(
                self.options.get("rate_limit_rps", 1.5)
            )
            if requests_per_second <= 0:
                requests_per_second = 1.5
            min_interval = 1.0 / requests_per_second
            last_request_ts = 0.0

            for path in paths:
                if self.isInterruptionRequested():
                    return
                content = _read_text_file_if_supported(path)
                if not content:
                    try:
                        resp = api_client.process_document(path)
                        content = extract_content_from_response(resp)
                    except requests.exceptions.RequestException as exc:
                        file_errors.append({"file": path, "error": f"API connection error: {exc}"})
                        continue
                    except json.JSONDecodeError as exc:
                        file_errors.append({"file": path, "error": f"Invalid API response: {exc}"})
                        continue
                    except Exception as exc:
                        logger.exception("Unexpected error processing document '%s': %s", path, exc)
                        file_errors.append({"file": path, "error": f"Unexpected error: {exc}"})
                        continue

                if not content.strip():
                    file_errors.append({"file": path, "error": "no_readable_text"})
                    continue

                now = time.monotonic()
                elapsed = now - last_request_ts
                if elapsed < min_interval:
                    time.sleep(min_interval - elapsed)

                model_plan = (
                    [requested_model]
                    if requested_model in {"auto", "gliner", "llm", "hf_ner", "spacy", "patterns"}
                    else ["auto"]
                )
                if requested_model != "auto":
                    model_plan.extend(["auto", "gliner", "patterns"])

                file_entities: list[dict] = []
                file_relationships: list[dict] = []
                for model_name in model_plan:
                    try:
                        body = api_client.extract_entities(
                            content,
                            entity_types=entity_types,
                            extraction_type="ner",
                            extra_options={
                                "extraction_model": model_name,
                                "provenance_requested": True,
                            },
                        )
                    except requests.exceptions.RequestException as exc:
                        file_errors.append({"file": path, "error": f"API connection error ({model_name}): {exc}"})
                        continue
                    except json.JSONDecodeError as exc:
                        file_errors.append({"file": path, "error": f"Invalid API response ({model_name}): {exc}"})
                        continue
                    except Exception as exc:
                        logger.exception("Unexpected error extracting entities with model '%s' from '%s': %s", model_name, path, exc)
                        file_errors.append({"file": path, "error": f"Unexpected error ({model_name}): {exc}"})
                        continue
                    
                    last_request_ts = time.monotonic()
                    data = body.get("data") if isinstance(body.get("data"), dict) else {}
                    per_stats = (
                        body.get("extraction_stats")
                        if isinstance(body.get("extraction_stats"), dict)
                        else data.get("extraction_stats")
                        if isinstance(data.get("extraction_stats"), dict)
                        else {}
                    )
                    if isinstance(per_stats.get("extraction_methods_used"), list):
                        methods_used.update(
                            str(m) for m in per_stats.get("extraction_methods_used", [])
                        )
                    entities = (
                        body.get("entities")
                        if isinstance(body.get("entities"), list)
                        else data.get("entities")
                    )
                    relationships = (
                        body.get("relationships")
                        if isinstance(body.get("relationships"), list)
                        else data.get("relationships")
                    )
                    if bool(body.get("success", True)) and isinstance(entities, list) and entities:
                        file_entities = entities
                        file_relationships = (
                            relationships if isinstance(relationships, list) else []
                        )
                        if model_name != requested_model:
                            file_errors.append(
                                {
                                    "file": path,
                                    "error": (
                                        f"fallback_used requested={requested_model} "
                                        f"used={model_name}"
                                    ),
                                }
                            )
                        break
                all_entities.extend(file_entities)
                all_relationships.extend(file_relationships)

                file_chunks.append(f"--- FILE: {path} ---\n{content}")
                total_processed += 1

            if total_processed == 0:
                raise RuntimeError(
                    "Folder extraction found no readable text in supported files."
                )
            warnings: list[str] = []
            if file_errors:
                warnings.append(f"{len(file_errors)} file(s) failed to process.")
            if requested_model == "gliner" and "gliner" not in methods_used:
                warnings.append(
                    "GLiNER requested but backend did not report GLiNER usage."
                )
            if requested_model == "llm" and "llm" not in methods_used:
                warnings.append(
                    "LLM requested but backend did not report LLM usage."
                )
            if len(all_entities) == 0:
                warnings.append("Folder extraction returned zero entities.")

            self.result_ready.emit(
                {
                    "success": True,
                    "error": None,
                    "source_text": "\n\n".join(file_chunks),
                    "entities": all_entities,
                    "relationships": all_relationships,
                    "extraction_stats": {
                        "files_total": len(paths),
                        "files_processed": total_processed,
                        "files_failed": len(file_errors),
                        "file_errors": file_errors[:50],
                        "extraction_methods_used": sorted(methods_used),
                        "warnings": warnings,
                        "total_entities": len(all_entities),
                        "total_relationships": len(all_relationships),
                    },
                }
            )
        except (FileNotFoundError, PermissionError, IOError) as e:
            self.error_occurred.emit(f"File system error: {e}")
        except requests.exceptions.RequestException as e:
            self.error_occurred.emit(f"API connection error: {e}")
        except json.JSONDecodeError as e:
            self.error_occurred.emit(f"Invalid API response: {e}")
        except RuntimeError as e:
            self.error_occurred.emit(str(e))
        except Exception as e:
            logger.exception("An unexpected error occurred during folder extraction: %s", e)
            self.error_occurred.emit(f"An unexpected error occurred: {e}")

class LegalReasoningWorker(QThread):
    """Worker thread for legal reasoning operations."""

    result_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(
        self,
        asyncio_thread,
        file_path,
        text_input,
        reasoning_type,
        folder_path: str = "",
        options: Optional[dict] = None,
    ):
        super().__init__()
        self.asyncio_thread = asyncio_thread
        self.file_path = file_path
        self.text_input = text_input
        self.reasoning_type = reasoning_type
        self.folder_path = folder_path
        self.options = options or {}

    @staticmethod
    def _map_reasoning_type(reasoning_type: str) -> str:
        mapping = {
            "General Analysis": "comprehensive",
            "Case Law Analysis": "case_law",
            "Statutory Interpretation": "statutory_interpretation",
            "Contract Analysis": "contract",
            "Precedent Analysis": "precedent",
            "Legal Risk Assessment": "risk_assessment",
        }
        return mapping.get(str(reasoning_type or "").strip(), "comprehensive")

    def run(self):  # noqa: C901
        """Execute legal reasoning via API."""
        try:
            if self.isInterruptionRequested():
                return
            if not requests:
                raise RuntimeError("requests not available")
            # Determine text to reason about
            content = self.text_input.strip()
            if not content and self.file_path:
                # Upload the file to get content
                resp = api_client.process_document(self.file_path)
                content = extract_content_from_response(resp)
            if not content and self.folder_path:
                content = _collect_folder_content_utility(self.folder_path, self.isInterruptionRequested)

            if not content:
                raise RuntimeError("No content to analyze")
            if self.isInterruptionRequested():
                return
            payload_options = dict(self.options)
            payload_options.pop("reasoning_type", None)
            payload_options["analysis_type"] = self._map_reasoning_type(
                self.reasoning_type
            )
            # Call legal reasoning endpoint
            body = api_client.analyze_legal_reasoning(content, payload_options)
            if not body.get("success", True):
                err = body.get("error") or "Legal reasoning failed"
                self.error_occurred.emit(str(err))
                return
            data = body.get("data") if isinstance(body.get("data"), dict) else {}
            if not data:
                details = body.get("details")
                data = details if isinstance(details, dict) else {}
            self.result_ready.emit(data)
        except (IOError, FileNotFoundError, PermissionError) as e:
            self.error_occurred.emit(f"File access error: {e}")
        except requests.exceptions.RequestException as e:
            self.error_occurred.emit(f"API connection error: {e}")
        except json.JSONDecodeError as e:
            self.error_occurred.emit(f"Invalid API response: {e}")
        except RuntimeError as e:
            self.error_occurred.emit(str(e))
        except Exception as e:
            logger.exception("An unexpected error occurred during legal reasoning: %s", e)
            self.error_occurred.emit(f"An unexpected error occurred: {e}")

class EmbeddingWorker(QThread):
    """Worker thread for embedding operations."""

    result_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(
        self,
        asyncio_thread,
        text,
        model_name,
        operation,
        options: Optional[dict] = None,
        file_path: str = "",
        folder_path: str = "",
    ):
        super().__init__()
        self.asyncio_thread = asyncio_thread
        self.text = text
        self.model_name = model_name
        self.operation = operation
        self.options = options or {}
        self.file_path = file_path
        self.folder_path = folder_path

    def run(self):  # noqa: C901
        """Execute embedding generation via API with local model mapping."""
        try:
            if self.isInterruptionRequested():
                return
            if not requests:
                raise RuntimeError("requests not available")

            content = self.text.strip()
            source = "text"
            if not content and self.file_path:
                resp = api_client.process_document(self.file_path)
                content = extract_content_from_response(resp).strip()
                source = "file"
            if not content and self.folder_path:
                content = _collect_folder_content_utility(
                    self.folder_path,
                    self.isInterruptionRequested,
                ).strip()
                source = "folder"
            if not content:
                raise RuntimeError("No content to embed")
            
            # Map UI labels to backend EmbeddingModel values
            mapping = {
                "Nomic v1.5 (High-Fidelity)": "nomic-ai/nomic-embed-text-v1.5",
                "MiniLM-L6 (Local-Fast)": "all-MiniLM-L6-v2",
                "Legal-BERT": "nlpaueb/legal-bert-base-uncased",
                "OpenAI": "text-embedding-3-small"
            }
            backend_model = mapping.get(self.model_name, self.model_name)
            
            # Call embedding endpoint
            body = api_client.run_embedding_operation(
                content,
                backend_model,
                self.operation,
                options=self.options,
            )
            result = body.get("data") or {}
            if isinstance(result, dict):
                result.setdefault("content_source", source)
                result.setdefault("input_characters", len(content))
            self.result_ready.emit(result)
        except (IOError, FileNotFoundError, PermissionError) as e:
            self.error_occurred.emit(f"File access error: {e}")
        except requests.exceptions.RequestException as e:
            self.error_occurred.emit(f"API connection error: {e}")
        except json.JSONDecodeError as e:
            self.error_occurred.emit(f"Invalid API response: {e}")
        except RuntimeError as e:
            self.error_occurred.emit(str(e))
        except Exception as e:
            logger.exception("An unexpected error occurred during embedding operation: %s", e)
            self.error_occurred.emit(f"An unexpected error occurred: {e}")

class DocumentOrganizationWorker(QThread):
    """Worker thread for document organization operations."""

    result_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, asyncio_thread, file_path, text_input, organization_type):
        super().__init__()
        self.asyncio_thread = asyncio_thread
        self.file_path = file_path
        self.text_input = text_input
        self.organization_type = organization_type

    def run(self):  # noqa: C901
        """Execute document organization via API."""
        try:
            if self.isInterruptionRequested():
                return
            if not requests:
                raise RuntimeError("requests not available")
            # Determine text to organize
            content = self.text_input.strip()
            if not content and self.file_path:
                # Upload the file to get content
                resp = api_client.process_document(self.file_path)
                content = extract_content_from_response(resp)
            
            if not content:
                raise RuntimeError("No content to organize")
            if self.isInterruptionRequested():
                return
            # Call document organization endpoint
            body = api_client.organize_document(content)
            self.result_ready.emit(body.get("data") or {})
        except (IOError, FileNotFoundError, PermissionError) as e:
            self.error_occurred.emit(f"File access error: {e}")
        except requests.exceptions.RequestException as e:
            self.error_occurred.emit(f"API connection error: {e}")
        except json.JSONDecodeError as e:
            self.error_occurred.emit(f"Invalid API response: {e}")
        except RuntimeError as e:
            self.error_occurred.emit(str(e))
        except Exception as e:
            logger.exception("An unexpected error occurred during document organization: %s", e)
            self.error_occurred.emit(f"An unexpected error occurred: {e}")

class VectorIndexWorker(QThread):
    """Worker thread for vector indexing operations."""

    result_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, asyncio_thread, file_path, text_input):
        super().__init__()
        self.asyncio_thread = asyncio_thread
        self.file_path = file_path
        self.text_input = text_input

    def run(self):  # noqa: C901
        """Execute vector indexing via API."""
        try:
            if self.isInterruptionRequested():
                return
            if not requests:
                raise RuntimeError("requests not available")
            # Determine text to index
            content = self.text_input.strip()
            if not content and self.file_path:
                # Upload the file to get content
                resp = api_client.process_document(self.file_path)
                content = extract_content_from_response(resp)
            
            if not content:
                raise RuntimeError("No content to index")
            if self.isInterruptionRequested():
                return
            # Call vector index endpoint
            body = api_client.index_to_vector(content)
            self.result_ready.emit(body.get("data") or {})
        except (IOError, FileNotFoundError, PermissionError) as e:
            self.error_occurred.emit(f"File access error: {e}")
        except requests.exceptions.RequestException as e:
            self.error_occurred.emit(f"API connection error: {e}")
        except json.JSONDecodeError as e:
            self.error_occurred.emit(f"Invalid API response: {e}")
        except RuntimeError as e:
            self.error_occurred.emit(str(e))
        except Exception as e:
            logger.exception("An unexpected error occurred during vector indexing: %s", e)
            self.error_occurred.emit(f"An unexpected error occurred: {e}")

class KGFromFilesWorker(QThread):
    progress_update = Signal(int, str)
    finished_ok = Signal(str)
    finished_err = Signal(str)

    def __init__(self, files):
        super().__init__()
        self.files = files

    def run(self):
        try:
            if self.isInterruptionRequested():
                return
            for i, file_path in enumerate(self.files):
                if self.isInterruptionRequested():
                    return
                self.progress_update.emit(i, "processing")
                # Process file to extract KG
                # Placeholder for KG extraction logic
                self.progress_update.emit(i, "done")
            self.finished_ok.emit("KG extraction completed")
        except (IOError, FileNotFoundError, PermissionError) as e:
            logger.error(f"[KGFromFilesWorker] File access error for {file_path}: {e}")
            self.finished_err.emit(f"File access error: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"[KGFromFilesWorker] API connection error for {file_path}: {e}")
            self.finished_err.emit(f"API connection error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"[KGFromFilesWorker] Invalid API response for {file_path}: {e}")
            self.finished_err.emit(f"Invalid API response: {e}")
        except RuntimeError as e:
            logger.error(f"[KGFromFilesWorker] Runtime error for {file_path}: {e}")
            self.finished_err.emit(str(e))
        except Exception as e:
            logger.exception(f"[KGFromFilesWorker] An unexpected error occurred for {file_path}: {e}")
            self.finished_err.emit(f"An unexpected error occurred: {e}")

class PipelineRunnerWorker(QThread):
    finished_ok = Signal(dict)
    finished_err = Signal(str)

    def __init__(self, preset: dict, path: str):
        super().__init__()
        self.preset = preset
        self.path = path

    def run(self):  # noqa: C901
        try:
            name = self.preset.get("name", "Unknown")
            logger.info(f"[PipelineRunnerWorker] Running pipeline '{name}' on '{self.path}'...")
            if self.isInterruptionRequested():
                return
            if not requests:
                raise RuntimeError("requests not available")
            if not self.path.strip():
                raise ValueError("No file provided for pipeline processing")
            
            logger.info("[PipelineRunnerWorker] Sending run request...")
            result = api_client.run_pipeline(self.preset, self.path)
            logger.info("[PipelineRunnerWorker] Pipeline completed successfully.")
            self.finished_ok.emit(result)
        except ValueError as e:
            logger.error(f"[PipelineRunnerWorker] Value error for {self.path}: {e}")
            self.finished_err.emit(f"Value error: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"[PipelineRunnerWorker] API connection error for {self.path}: {e}")
            self.finished_err.emit(f"API connection error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"[PipelineRunnerWorker] Invalid API response for {self.path}: {e}")
            self.finished_err.emit(f"Invalid API response: {e}")
        except RuntimeError as e:
            logger.error(f"[PipelineRunnerWorker] Runtime error for {self.path}: {e}")
            self.finished_err.emit(str(e))
        except Exception as e:
            logger.exception(f"[PipelineRunnerWorker] An unexpected error occurred for {self.path}: {e}")
            self.finished_err.emit(f"An unexpected error occurred: {e}")

class FetchOntologyWorker(QThread):
    finished_ok = Signal(list)
    finished_err = Signal(str)

    def __init__(self):
        super().__init__()

    def run(self):
        try:
            logger.info("[FetchOntologyWorker] Starting...")
            if not requests:
                raise RuntimeError("requests not available")
            
            logger.info("[FetchOntologyWorker] Calling api_client.get_ontology_entities()...")
            result = api_client.get_ontology_entities()
            # result structure from routes/ontology.py: {"items": [{"label": ..., ...}], ...}
            items = result.get("items", [])
            logger.info(f"[FetchOntologyWorker] Got {len(items)} ontology items.")
            self.finished_ok.emit(items)
        except requests.exceptions.RequestException as e:
            logger.error(f"[FetchOntologyWorker] API connection error: {e}")
            self.finished_err.emit(f"API connection error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"[FetchOntologyWorker] Invalid API response: {e}")
            self.finished_err.emit(f"Invalid API response: {e}")
        except RuntimeError as e:
            logger.error(f"[FetchOntologyWorker] Runtime error: {e}")
            self.finished_err.emit(str(e))
        except Exception as e:
            logger.exception(f"[FetchOntologyWorker] An unexpected error occurred: {e}")
            self.finished_err.emit(f"An unexpected error occurred: {e}")
