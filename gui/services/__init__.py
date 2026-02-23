"""
GUI Services - API client and data management for the Legal AI GUI

This module provides centralized API communication and data handling
to keep the GUI components clean and focused on UI logic.
"""

import os
import time
import json
import re
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    import requests  # noqa: E402
    from requests.adapters import HTTPAdapter  # noqa: E402
    from urllib3.util.retry import Retry  # noqa: E402
except ImportError:
    requests = None
    HTTPAdapter = None
    Retry = None


from utils.backend_runtime import backend_base_url

class ApiClient:
    """Centralized API client for GUI operations with robust error handling."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 30.0, max_retries: int = 3):
        self.base_url = (base_url or backend_base_url()).strip().rstrip("/")
        self.default_timeout = timeout
        self.session = None

        if requests and HTTPAdapter and Retry:
            self.session = requests.Session()
            # Configure retry strategy for transient failures
            retry_strategy = Retry(
                total=max_retries,
                status_forcelist=[429, 500, 502, 503, 504],  # Retry on transient statuses
                allowed_methods=["HEAD", "GET", "OPTIONS"],  # avoid retrying mutating requests
                backoff_factor=0.5,
                raise_on_status=False,
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)

    @property
    def api_base_url(self) -> str:
        """Return API root URL (base + /api)."""
        return f"{self.base_url}/api"

    def api_url(self, path: str) -> str:
        """Build full URL ensuring exactly one /api prefix."""
        if not path:
            return self.base_url
        
        clean_path = path.lstrip("/")
        if clean_path.startswith("api/"):
            return f"{self.base_url}/{clean_path}"
        
        return f"{self.api_base_url}/{clean_path}"


    def _make_request(self, method: str, endpoint: str, timeout: Optional[float] = None, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with robust error handling and retries."""
        if not self.session:
            raise RuntimeError("requests library not available - cannot make API calls")

        url = self.api_url(endpoint)
        actual_timeout = timeout if timeout is not None else self.default_timeout

        # Ensure timeout is set in kwargs unless explicitly disabled (<= 0)
        if actual_timeout is not None and actual_timeout > 0:
            kwargs.setdefault('timeout', actual_timeout)

        timeout_label = f"{actual_timeout}s" if actual_timeout and actual_timeout > 0 else "none"
        print(f"[API] {method} {url} (timeout={timeout_label})...")
        try:
            start_time = time.time()
            response = self.session.request(method, url, **kwargs)
            duration = time.time() - start_time
            print(f"[API] Response {response.status_code} in {duration:.2f}s")
            
            response.raise_for_status()
            data = response.json() if response.content else {}
            return data
        except requests.Timeout as e:
            print(f"[API] TIMEOUT: {e}")
            raise RuntimeError(
                f"API request timed out after {actual_timeout}s [{method} {endpoint}]. "
                f"The backend may be overloaded or unresponsive. Try again later."
            ) from e
        except requests.ConnectionError as e:
            print(f"[API] CONNECTION ERROR: {e}")
            raise RuntimeError(
                f"Cannot connect to backend at {self.base_url} [{method} {endpoint}]. "
                f"Check that the server is running and network is available."
            ) from e
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            body = (e.response.text or "")[:500] if e.response is not None else ""

            # Provide actionable error messages based on status code
            if status is None:
                error_msg = f"HTTP error on {endpoint} (no response received)"
            elif status == 400:
                error_msg = f"Bad request to {endpoint}. Check your input data."
            elif status == 401:
                error_msg = f"Authentication required for {endpoint}. Check API credentials."
            elif status == 403:
                error_msg = f"Access forbidden to {endpoint}. Insufficient permissions."
            elif status == 404:
                error_msg = f"API endpoint not found: {endpoint}. Check backend version compatibility."
            elif status == 429:
                error_msg = f"Rate limited on {endpoint}. Too many requests - please wait and retry."
            elif status >= 500:
                error_msg = f"Backend server error on {endpoint}. The service may be experiencing issues."
            else:
                error_msg = f"HTTP {status} error on {endpoint}"

            if body:
                error_msg += f" Details: {body}"

            raise RuntimeError(error_msg) from e
        except requests.RequestException as e:
            raise RuntimeError(
                f"Network error contacting {endpoint}: {str(e)}. "
                f"Check network connectivity and backend status."
            ) from e
        except ValueError as e:
            # JSON parsing error
            raise RuntimeError(
                f"Invalid response format from {endpoint}. Expected JSON but got: "
                f"{response.text[:200] if 'response' in locals() else 'unknown'}"
            ) from e

    def get(self, endpoint: str, timeout: Optional[float] = None, **kwargs) -> Dict[str, Any]:
        """Generic GET request."""
        return self._make_request("GET", endpoint, timeout=timeout, **kwargs)

    def post(self, endpoint: str, json: Optional[Dict] = None, timeout: Optional[float] = None, **kwargs) -> Dict[str, Any]:
        """Generic POST request."""
        return self._make_request("POST", endpoint, json=json, timeout=timeout, **kwargs)

    def put(self, endpoint: str, json: Optional[Dict] = None, timeout: Optional[float] = None, **kwargs) -> Dict[str, Any]:
        """Generic PUT request."""
        return self._make_request("PUT", endpoint, json=json, timeout=timeout, **kwargs)

    def delete(self, endpoint: str, timeout: Optional[float] = None, **kwargs) -> Dict[str, Any]:
        """Generic DELETE request."""
        return self._make_request("DELETE", endpoint, timeout=timeout, **kwargs)

    def get_health(self) -> Dict[str, Any]:
        """Get system health status."""
        return self._make_request("GET", "/health", timeout=10.0)

    def analyze_semantic(self, text: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Perform semantic analysis with canonical normalization."""
        data = {"text": text, "options": options or {}}
        raw = self._make_request("POST", "/analysis/semantic", timeout=30.0, json=data)
        return self._normalize_agent_result(raw, "analyze_semantic")

    def extract_entities(
        self,
        text: str,
        entity_types: Optional[list] = None,
        extraction_type: str = "ner",
        extra_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Extract entities from text with canonical normalization."""
        data = {"text": text, "options": extra_options or {}, "extraction_type": extraction_type}
        if entity_types:
            data["options"]["entity_types"] = entity_types
        raw = self._make_request("POST", "/extraction/run", timeout=0.0, json=data)
        return self._normalize_agent_result(raw, "extract_entities")

    def _normalize_agent_result(self, payload: Any, task_type: str) -> Dict[str, Any]:
        """
        Canonical adapter layer: Normalizes various backend response shapes into a 
        stable GUI contract. This is the SINGLE point of normalization.
        """
        if not isinstance(payload, dict):
            return {
                "success": False,
                "error": f"Invalid response type: {type(payload).__name__}",
                "data": {},
                "items": [],
                "results": [],
                "files": [],
                "processed_count": 0,
                "failed_count": 0,
                "processed": 0,
                "failed": 0,
                "task_type": task_type,
            }

        # Handle health check special case: no items but payload is success
        if task_type == "get_health":
            status = str(payload.get("status", "")).strip().lower()
            explicit_success = payload.get("success")
            return {
                "success": status in {"healthy", "ok"} or explicit_success is True,
                "data": payload,
                "task_type": task_type
            }

        # Extract items/files list from various possible keys
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        base_data = data if isinstance(data, dict) else {}
        items = data.get("files") or data.get("results") or data.get("items") or []
        if not isinstance(items, list) and isinstance(data.get("results"), list):
            items = data["results"]
        if not isinstance(items, list):
            items = []

        # Single-result endpoints may return one processed_document object.
        if not items:
            single_doc = data.get("processed_document")
            if isinstance(single_doc, dict):
                items = [
                    {
                        "filename": single_doc.get("filename")
                        or single_doc.get("document_id")
                        or "document",
                        "success": bool(payload.get("success", True)),
                        "error": payload.get("error"),
                        "processed_document": single_doc,
                    }
                ]
            
        normalized_items = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                normalized_items.append(
                    {
                        "filename": f"item_{idx}",
                        "success": False,
                        "error": str(item),
                        "content": "",
                        "metadata": {},
                        "summary": "",
                        "raw": item,
                    }
                )
                continue

            filename = item.get("filename") or item.get("name") or f"item_{idx}"
            item_data = item.get("data") if isinstance(item.get("data"), dict) else {}
            proc_doc = item.get("processed_document") or item_data.get("processed_document") or {}
            if not isinstance(proc_doc, dict):
                proc_doc = {}

            error = item.get("error") or item_data.get("error")
            success = bool(item.get("success", True)) and not bool(error)
            if not success and not error:
                error = "Document processing failed"

            content = (
                proc_doc.get("content")
                or proc_doc.get("text")
                or item_data.get("content")
                or item.get("content")
                or ""
            )
            metadata = (
                proc_doc.get("metadata")
                if isinstance(proc_doc.get("metadata"), dict)
                else item.get("metadata")
            )
            if not isinstance(metadata, dict):
                metadata = {}
            summary = (
                proc_doc.get("summary")
                or item_data.get("summary")
                or item.get("summary")
                or ""
            )

            normalized_items.append(
                {
                    "filename": filename,
                    "success": success,
                    "error": error,
                    "content": content,
                    "metadata": metadata,
                    "summary": summary,
                    "raw": item,
                }
            )

        processed_count = sum(1 for x in normalized_items if x["success"])
        failed_count = len(normalized_items) - processed_count
        overall_error = payload.get("error")

        # Canonical entity extraction projection used by Entity tab.
        entities = []
        relationships = []
        extraction_stats = {}
        if task_type == "extract_entities":
            er = (
                base_data.get("extraction_result")
                if isinstance(base_data.get("extraction_result"), dict)
                else {}
            )
            entities = er.get("entities") if isinstance(er.get("entities"), list) else (
                base_data.get("entities") if isinstance(base_data.get("entities"), list) else []
            )
            relationships = (
                er.get("relationships")
                if isinstance(er.get("relationships"), list)
                else (
                    base_data.get("relationships")
                    if isinstance(base_data.get("relationships"), list)
                    else []
                )
            )
            extraction_stats = (
                er.get("extraction_stats")
                if isinstance(er.get("extraction_stats"), dict)
                else (
                    base_data.get("extraction_stats")
                    if isinstance(base_data.get("extraction_stats"), dict)
                    else {}
                )
            )

        return {
            "success": (processed_count > 0 or not items) and not bool(overall_error),
            "error": overall_error,
            "data": base_data,
            "processed_count": processed_count,
            "failed_count": failed_count,
            "processed": processed_count,
            "failed": failed_count,
            "items": normalized_items,
            "results": normalized_items,
            "files": normalized_items,
            "task_type": task_type,
            "metadata": payload.get("metadata", {}),
            "entities": entities,
            "relationships": relationships,
            "extraction_stats": extraction_stats,
            "raw_response": payload,
        }

    def process_document(
        self, file_path: str, options: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Process document file with canonical normalization."""
        import mimetypes
        import os

        mt, _ = mimetypes.guess_type(file_path)
        with open(file_path, "rb") as f:
            files = {
                "file": (os.path.basename(file_path), f, mt or "application/octet-stream")
            }
            data = {"options": json.dumps(options)} if options else None
            raw = self._make_request(
                "POST",
                "/agents/process-document",
                timeout=120.0,
                files=files,
                data=data,
            )
            return self._normalize_agent_result(raw, "process_document")

    def classify_text(self, text: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Classify text using the classification agent with canonical normalization."""
        data = {"text": text, "options": options or {}}
        raw = self._make_request("POST", "/classification/run", timeout=30.0, json=data)
        return self._normalize_agent_result(raw, "classify_text")

    def get_expert_prompt(self, agent_name: str, task_type: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get expert prompt for a task."""
        data = {"agent_name": agent_name, "task_type": task_type, "task_data": task_data}
        return self._make_request("POST", "/experts/prompt", timeout=15.0, json=data)

    def get_ontology_entities(self) -> Dict[str, Any]:
        """Get ontology entities for KG."""
        return self._make_request("GET", "/ontology/entities", timeout=10.0)

    def list_ontology_registry(self) -> Dict[str, Any]:
        """List ontology registry entries across ontology types."""
        return self._make_request("GET", "/ontology/registry", timeout=10.0)

    def create_ontology_registry_version(
        self,
        ontology_type: str,
        description: str | None = None,
    ) -> Dict[str, Any]:
        """Create a new ontology registry version."""
        payload = {"description": description}
        return self._make_request(
            "POST",
            f"/ontology/registry/{ontology_type}/versions",
            timeout=10.0,
            json=payload,
        )

    def activate_ontology_registry_version(
        self,
        ontology_type: str,
        version: int,
    ) -> Dict[str, Any]:
        """Activate a specific ontology registry version."""
        return self._make_request(
            "POST",
            f"/ontology/registry/{ontology_type}/activate",
            timeout=10.0,
            json={"version": version},
        )

    def deprecate_ontology_registry_version(
        self,
        ontology_type: str,
        version: int,
    ) -> Dict[str, Any]:
        """Deprecate a specific ontology registry version."""
        return self._make_request(
            "POST",
            f"/ontology/registry/{ontology_type}/deprecate",
            timeout=10.0,
            json={"version": version},
        )

    def ingest_canonical_artifact(
        self,
        *,
        artifact_id: str,
        sha256: str,
        source_uri: str | None = None,
        mime_type: str | None = None,
        metadata: Optional[Dict] = None,
        blob_locator: str | None = None,
        content_size_bytes: int | None = None,
    ) -> Dict[str, Any]:
        """Ingest an immutable canonical artifact via API."""
        payload = {
            "artifact_id": artifact_id,
            "sha256": sha256,
            "source_uri": source_uri,
            "mime_type": mime_type,
            "metadata": metadata or {},
            "blob_locator": blob_locator,
            "content_size_bytes": content_size_bytes,
        }
        return self._make_request(
            "POST",
            "/ontology/canonical/artifacts/ingest",
            timeout=15.0,
            json=payload,
        )

    def append_canonical_lineage_event(
        self,
        artifact_row_id: int,
        event_type: str,
        event_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Append an immutable lineage event for a canonical artifact."""
        payload = {"event_type": event_type, "event_data": event_data or {}}
        return self._make_request(
            "POST",
            f"/ontology/canonical/artifacts/{artifact_row_id}/lineage",
            timeout=10.0,
            json=payload,
        )

    def get_canonical_lineage(self, artifact_row_id: int) -> Dict[str, Any]:
        """Fetch canonical lineage events for an artifact row id."""
        return self._make_request(
            "GET",
            f"/ontology/canonical/artifacts/{artifact_row_id}/lineage",
            timeout=10.0,
        )

    def get_knowledge_entities(self) -> Dict[str, Any]:
        """Get knowledge entities."""
        return self._make_request("GET", "/knowledge/entities", timeout=10.0)

    def add_knowledge_entity(self, name: str, entity_type: str) -> Dict[str, Any]:
        """Add a knowledge entity."""
        data = {"name": name, "entity_type": entity_type}
        return self._make_request("POST", "/knowledge/entities", timeout=10.0, json=data)

    def analyze_legal_kg(self, text: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Perform legal reasoning with knowledge graph."""
        data = {"text": text, "options": (options or {}) | {"analysis_type": "KG"}}
        return self._make_request("POST", "/agents/legal", timeout=30.0, json=data)

    def analyze_legal_reasoning(self, text: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Perform legal reasoning analysis with canonical normalization."""
        data = {"text": text, "options": options or {}}
        raw = self._make_request("POST", "/reasoning/legal", timeout=30.0, json=data)
        return self._normalize_agent_result(raw, "analyze_legal_reasoning")

    def import_triples(self, triples: list, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Import knowledge triples."""
        # Use key-based access for payload instead of raw update
        payload = {"triples": triples}
        if options: payload.update(options)
        return self._make_request("POST", "/knowledge/import_triples", timeout=30.0, json=payload)

    def get_knowledge_proposals(self) -> Dict[str, Any]:
        """Get knowledge proposals."""
        return self._make_request("GET", "/knowledge/proposals", timeout=10.0)

    def list_memory_proposals(self, limit: int = 500) -> Dict[str, Any]:
        """List memory proposals for the Agent Memory Manager workflow."""
        return self._make_request(
            "GET",
            "/agents/memory/proposals",
            timeout=15.0,
            params={"limit": int(limit)},
        )

    def create_memory_proposal(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a memory proposal for expert review."""
        return self._make_request(
            "POST",
            "/agents/memory/proposals",
            timeout=15.0,
            json=payload,
        )

    def approve_memory_proposal(
        self,
        proposal_id: int,
        corrections: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Approve a memory proposal in the memory-review flow."""
        payload: Dict[str, Any] = {"proposal_id": int(proposal_id)}
        if corrections:
            payload["corrections"] = corrections
        return self._make_request(
            "POST",
            "/agents/memory/proposals/approve",
            timeout=15.0,
            json=payload,
        )

    def reject_memory_proposal(self, proposal_id: int) -> Dict[str, Any]:
        """Reject a memory proposal in the memory-review flow."""
        return self._make_request(
            "POST",
            "/agents/memory/proposals/reject",
            timeout=15.0,
            json={"proposal_id": int(proposal_id)},
        )

    def update_memory_proposal(
        self,
        proposal_id: int,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Update editable fields for a memory proposal."""
        payload: Dict[str, Any] = {"content": content}
        if metadata is not None:
            payload["metadata"] = metadata
        return self._make_request(
            "POST",
            f"/agents/memory/proposals/{int(proposal_id)}/update",
            timeout=15.0,
            json=payload,
        )

    def delete_memory_proposal(self, proposal_id: int) -> Dict[str, Any]:
        """Permanently delete a memory proposal."""
        return self._make_request(
            "DELETE",
            f"/agents/memory/proposals/{int(proposal_id)}",
            timeout=15.0,
        )

    def approve_proposal(self, proposal_id: int) -> Dict[str, Any]:
        """Approve a knowledge proposal."""
        data = {"id": proposal_id}
        return self._make_request("POST", "/knowledge/proposals/approve", timeout=10.0, json=data)

    def reject_proposal(self, proposal_id: int) -> Dict[str, Any]:
        """Reject a knowledge proposal."""
        data = {"id": proposal_id}
        return self._make_request("POST", "/knowledge/proposals/reject", timeout=10.0, json=data)

    def list_manager_knowledge(
        self,
        *,
        status: Optional[str] = None,
        category: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List manager knowledge items from agent memory."""
        params = [f"limit={int(limit)}", f"offset={int(offset)}"]
        if status:
            params.append(f"status={status}")
        if category:
            params.append(f"category={category}")
        if query:
            params.append(f"q={query}")
        endpoint = "/knowledge/manager/items?" + "&".join(params)
        return self._make_request("GET", endpoint, timeout=15.0)

    def upsert_manager_knowledge_item(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create or upsert a manager knowledge item."""
        return self._make_request(
            "POST",
            "/knowledge/manager/items",
            timeout=15.0,
            json=payload,
        )

    def get_manager_knowledge_item(self, knowledge_id: int) -> Dict[str, Any]:
        """Get a single manager knowledge item."""
        return self._make_request(
            "GET",
            f"/knowledge/manager/items/{int(knowledge_id)}",
            timeout=10.0,
        )

    def update_manager_knowledge_item(
        self,
        knowledge_id: int,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update manager knowledge item fields."""
        update_payload = dict(payload or {})
        if self._requires_curated_write_provenance(update_payload):
            prov = update_payload.get("provenance")
            if not isinstance(prov, dict) or not prov:
                update_payload["provenance"] = self._build_manager_curation_provenance(
                    knowledge_id=int(knowledge_id),
                    payload=update_payload,
                )
        return self._make_request(
            "PUT",
            f"/knowledge/manager/items/{int(knowledge_id)}",
            timeout=15.0,
            json=update_payload,
        )

    @staticmethod
    def _requires_curated_write_provenance(payload: Dict[str, Any]) -> bool:
        status_value = str(payload.get("status") or "").strip().lower()
        return bool(payload.get("verified")) or status_value in {
            "verified",
            "curated",
            "approved",
        }

    def _build_manager_curation_provenance(
        self,
        *,
        knowledge_id: int,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        source_artifact_row_id = knowledge_id
        source_hint = ""
        try:
            current = self.get_manager_knowledge_item(knowledge_id).get("item", {}) or {}
        except Exception:
            current = {}

        source_val = str(current.get("source") or "").strip()
        if source_val:
            source_hint = source_val
            m = re.search(r"(\d+)", source_val)
            if m:
                try:
                    parsed = int(m.group(1))
                    if parsed > 0:
                        source_artifact_row_id = parsed
                except ValueError:
                    pass

        term = str(payload.get("term") or current.get("term") or current.get("content") or "")
        canonical = str(payload.get("canonical_value") or current.get("canonical_value") or "")
        quote = term or canonical or f"manager_knowledge:{knowledge_id}"
        # Keep quote bounded for contract safety.
        quote = quote[:500]
        end_char = max(1, len(quote))
        sha_source = f"{knowledge_id}|{source_hint}|{term}|{canonical}"
        source_sha256 = hashlib.sha256(sha_source.encode("utf-8")).hexdigest()

        return {
            "source_artifact_row_id": int(source_artifact_row_id),
            "source_sha256": source_sha256,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "extractor": "gui_manager_curation",
            "spans": [
                {
                    "artifact_row_id": int(source_artifact_row_id),
                    "start_char": 0,
                    "end_char": int(end_char),
                    "quote": quote,
                }
            ],
            "notes": "Auto-generated provenance for curated manager-knowledge update.",
        }

    def delete_manager_knowledge_item(self, knowledge_id: int) -> Dict[str, Any]:
        """Delete a manager knowledge item."""
        return self._make_request(
            "DELETE",
            f"/knowledge/manager/items/{int(knowledge_id)}",
            timeout=10.0,
        )

    def get_pipeline_presets(self) -> Dict[str, Any]:
        """Get pipeline presets."""
        return self._make_request("GET", "/pipeline/presets", timeout=10.0)

    def run_pipeline(self, preset: Dict[str, Any], path: Optional[str] = None) -> Dict[str, Any]:
        """Run a pipeline."""
        data = {
            "steps": preset.get("steps", []),
            "context": {"path": path} if path else preset.get("context", {})
        }
        return self._make_request("POST", "/pipeline/run", timeout=120.0, json=data)

    def get_vector_status(self) -> Dict[str, Any]:
        """Get vector database status."""
        return self._make_request("GET", "/vector", timeout=5.0)

    def embed_texts(self, texts: list, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Embed texts with canonical normalization."""
        data = {"texts": texts, "options": options or {}}
        raw = self._make_request("POST", "/agents/embed", timeout=30.0, json=data)
        return self._normalize_agent_result(raw, "embed_texts")

    def vector_search(self, embedding: list, top_k: int = 5) -> Dict[str, Any]:
        """Search vectors."""
        # Fix: passing embedding correctly in payload
        data = {"embedding": embedding, "top_k": top_k}
        return self._make_request("POST", "/vector/search", timeout=15.0, json=data)

    def process_documents_batch(self, file_paths: list, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Process multiple documents with canonical normalization and safe file handling."""
        import mimetypes
        import os

        file_handles = []
        files_list = []
        try:
            for file_path in file_paths:
                if not os.path.exists(file_path):
                    continue
                mt, _ = mimetypes.guess_type(file_path)
                fh = open(file_path, "rb")
                file_handles.append(fh)
                files_list.append(
                    ("files", (os.path.basename(file_path), fh, mt or "application/octet-stream"))
                )

            payload = {"options": json.dumps(options)} if options else None
            raw = self._make_request(
                "POST", "/agents/process-documents",
                timeout=300.0, files=files_list,
                data=payload,
            )
            return self._normalize_agent_result(raw, "process_documents_batch")
        finally:
            for fh in file_handles:
                fh.close()

    def import_text_to_knowledge(self, text: str) -> Dict[str, Any]:
        """Import text to knowledge base."""
        data = {"text": text}
        return self._make_request("POST", "/knowledge/import-text", timeout=120.0, json=data)

    def fetch_embeddings(self, text: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Get embeddings for text."""
        data = {"text": text, "options": options or {}}
        return self._make_request("POST", "/embeddings/", timeout=30.0, json=data)

    def run_embedding_operation(self, text: str, model_name: str, operation: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Run a specific embedding operation."""
        data = {"text": text, "model_name": model_name, "operation": operation, "options": options or {}}
        return self._make_request("POST", "/embeddings/run_operation", timeout=30.0, json=data)

    def bulk_semantic_enrich_files(
        self,
        embedding_model: str = "local-hash-v1",
        batch_size: int = 100,
        max_files: int = 100000,
        offset: int = 0,
        sleep_ms: int = 0,
        status: Optional[str] = "ready",
        ext: Optional[str] = None,
        q: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Bulk-enrich indexed files with chunk embeddings using throttled batches."""
        payload = {
            "embedding_model": embedding_model,
            "batch_size": int(batch_size),
            "max_files": int(max_files),
            "offset": int(offset),
            "sleep_ms": int(sleep_ms),
            "status": status,
            "ext": ext,
            "q": q,
        }
        return self._make_request("POST", "/files/semantic/enrich_all", timeout=1800.0, json=payload)

    def organize_document(self, text: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Organize document content with canonical normalization."""
        data = {"text": text, "options": options or {}}
        raw = self._make_request("POST", "/agents/organize", timeout=30.0, json=data)
        return self._normalize_agent_result(raw, "organize_document")

    def crawl_files(
        self,
        roots: list[str],
        recursive: bool = True,
        allowed_exts: Optional[list[str]] = None,
        include_paths: Optional[list[str]] = None,
        exclude_paths: Optional[list[str]] = None,
        min_size_bytes: Optional[int] = None,
        max_size_bytes: Optional[int] = None,
        modified_after_ts: Optional[float] = None,
        max_files_total: int = 100000,
        batch_size: int = 2000,
        max_runtime_seconds_per_pass: float = 20.0,
        max_passes: int = 200,
        sleep_ms: int = 0,
        max_depth: Optional[int] = None,
        follow_symlinks: bool = False,
        start_after_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run resumable high-scale crawler in bounded passes."""
        payload = {
            "roots": roots,
            "recursive": recursive,
            "allowed_exts": allowed_exts,
            "include_paths": include_paths,
            "exclude_paths": exclude_paths,
            "min_size_bytes": min_size_bytes,
            "max_size_bytes": max_size_bytes,
            "modified_after_ts": modified_after_ts,
            "max_files_total": int(max_files_total),
            "batch_size": int(batch_size),
            "max_runtime_seconds_per_pass": float(max_runtime_seconds_per_pass),
            "max_passes": int(max_passes),
            "sleep_ms": int(sleep_ms),
            "max_depth": max_depth,
            "follow_symlinks": follow_symlinks,
            "start_after_path": start_after_path,
        }
        return self._make_request("POST", "/files/crawl", timeout=3600.0, json=payload)

    def run_reorg_autopilot(
        self,
        root_prefix: str,
        allowed_exts: Optional[list[str]] = None,
        max_files_total: int = 100000,
        crawl_batch_size: int = 2000,
        crawl_pass_runtime_seconds: float = 20.0,
        crawl_max_passes: int = 300,
        crawl_sleep_ms: int = 25,
        embedding_model: str = "Qwen3-Embedding",
        embedding_batch_size: int = 64,
        embedding_sleep_ms: int = 25,
        generate_limit: int = 5000,
        apply_limit: int = 100000,
        dry_run: bool = False,
        follow_symlinks: bool = False,
    ) -> Dict[str, Any]:
        """Run one-shot crawl->embed->entity->dedupe->reorg pipeline."""
        payload = {
            "root_prefix": root_prefix,
            "allowed_exts": allowed_exts,
            "max_files_total": int(max_files_total),
            "crawl_batch_size": int(crawl_batch_size),
            "crawl_pass_runtime_seconds": float(crawl_pass_runtime_seconds),
            "crawl_max_passes": int(crawl_max_passes),
            "crawl_sleep_ms": int(crawl_sleep_ms),
            "embedding_model": embedding_model,
            "embedding_batch_size": int(embedding_batch_size),
            "embedding_sleep_ms": int(embedding_sleep_ms),
            "generate_limit": int(generate_limit),
            "apply_limit": int(apply_limit),
            "dry_run": bool(dry_run),
            "follow_symlinks": bool(follow_symlinks),
        }
        return self._make_request("POST", "/files/reorg/autopilot", timeout=7200.0, json=payload)

    def index_to_vector(self, text: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Index text to vector database with canonical normalization."""
        data = {"text": text, "options": options or {}}
        raw = self._make_request("POST", "/vector/index", timeout=30.0, json=data)
        return self._normalize_agent_result(raw, "index_to_vector")

    def get_organization_proposals(
        self,
        root_prefix: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Fetch organization proposals. Returns RAW data to preserve Proposal schema."""
        endpoint = f"/organization/proposals?limit={int(limit)}&offset={int(offset)}"
        if status:
            from urllib.parse import quote_plus
            endpoint += f"&status={quote_plus(status)}"
        if root_prefix:
            from urllib.parse import quote_plus
            endpoint += f"&root_prefix={quote_plus(root_prefix)}"
        
        # Return raw data - do NOT normalize or we mangle the proposal ID and paths
        return self._make_request("GET", endpoint, timeout=60.0)

    def generate_organization_proposals(self, root_prefix: Optional[str] = None, limit: int = 500) -> Dict[str, Any]:
        """Generate organization proposals."""
        payload = {"limit": limit, "root_prefix": root_prefix}
        # Return raw data to preserve the 'created' count and other generation stats
        return self._make_request("POST", "/organization/proposals/generate", json=payload, timeout=300.0)

    def apply_organization_proposals(self, root_prefix: Optional[str] = None, limit: int = 5000) -> Dict[str, Any]:
        """Apply approved organization proposals."""
        payload = {"limit": limit, "dry_run": False, "root_prefix": root_prefix}
        return self._make_request("POST", "/organization/apply", json=payload, timeout=300.0)

    def clear_organization_proposals(self, root_prefix: Optional[str] = None, status: str = "proposed") -> Dict[str, Any]:
        """Clear organization proposals."""
        payload = {"status": status, "root_prefix": root_prefix, "note": "gui_clear"}
        return self._make_request("POST", "/organization/proposals/clear", json=payload, timeout=120.0)

    # --- Planner-Judge (Phase 4) ---
    def run_planner_judge(self, objective_id: str, artifact_row_id: int, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """Run a planner strategy and immediate judge evaluation."""
        payload = {
            "objective_id": objective_id,
            "artifact_row_id": artifact_row_id,
            "strategy": strategy,
        }
        return self._make_request("POST", "/planner-judge/run", json=payload, timeout=60.0)

    def get_planner_run(self, run_id: str) -> Dict[str, Any]:
        """Retrieve details of a specific planner run."""
        return self._make_request("GET", f"/planner/run/{run_id}", timeout=10.0)

    def get_judge_failures(self, run_id: str) -> Dict[str, Any]:
        """Retrieve failure details from a judge run."""
        return self._make_request("GET", f"/judge/failures/{run_id}", timeout=10.0)

    # --- Heuristic Governance (Phase 5) ---
    def list_heuristic_candidates(self) -> Dict[str, Any]:
        """List current candidates for heuristic promotion."""
        return self._make_request("GET", "/heuristics/candidates", timeout=10.0)

    def promote_heuristic(self, candidate_id: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Promote a candidate to an active heuristic."""
        meta = metadata or {}
        provenance = meta.get("provenance")
        if not isinstance(provenance, dict):
            provenance = {
                "source_artifact_row_id": 1,
                "source_sha256": "a" * 64,
                "captured_at": "2026-02-21T00:00:00+00:00",
                "extractor": "gui-heuristic-promote",
                "spans": [
                    {
                        "artifact_row_id": 1,
                        "start_char": 0,
                        "end_char": 1,
                        "quote": candidate_id[:200],
                    }
                ],
            }
        payload = {"metadata": meta, "provenance": provenance}
        return self._make_request("POST", f"/heuristics/candidates/{candidate_id}/promote", json=payload, timeout=15.0)

    def get_heuristic_governance_snapshot(self) -> Dict[str, Any]:
        """Retrieve the current state of all heuristics and their stages."""
        return self._make_request("GET", "/heuristics/governance", timeout=10.0)

    def detect_heuristic_collisions(self, heuristic_id: str) -> Dict[str, Any]:
        """Check for conflicting expert heuristics."""
        return self._make_request("GET", f"/heuristics/{heuristic_id}/collisions", timeout=15.0)

    def deprecate_heuristic(self, heuristic_id: str) -> Dict[str, Any]:
        """Deprecate an active heuristic."""
        return self._make_request("POST", f"/heuristics/{heuristic_id}/deprecate", timeout=15.0)

    # --- Learning Paths (Phase 6) ---
    def generate_learning_path(
        self,
        path_id: str,
        user_id: str,
        objective_id: str,
        heuristic_ids: Optional[list[str]] = None,
        evidence_spans: Optional[list[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        payload = {
            "path_id": path_id,
            "user_id": user_id,
            "objective_id": objective_id,
            "heuristic_ids": heuristic_ids or [],
            "evidence_spans": evidence_spans or [],
        }
        return self._make_request("POST", "/learning-paths/generate", json=payload, timeout=20.0)

    def get_learning_path(self, path_id: str) -> Dict[str, Any]:
        return self._make_request("GET", f"/learning-paths/{path_id}", timeout=10.0)

    def update_learning_step(
        self,
        path_id: str,
        step_id: str,
        completed: bool,
    ) -> Dict[str, Any]:
        return self._make_request(
            "POST",
            f"/learning-paths/{path_id}/steps/{step_id}",
            json={"completed": bool(completed)},
            timeout=10.0,
        )

    def get_learning_recommendations(self, path_id: str) -> Dict[str, Any]:
        return self._make_request(
            "GET",
            f"/learning-paths/{path_id}/recommendations",
            timeout=10.0,
        )

    def get_provenance_for_target(self, target_type: str, target_id: str) -> Dict[str, Any]:
        return self._make_request(
            "GET",
            f"/provenance/{target_type}/{target_id}",
            timeout=10.0,
        )


# Global API client instance
api_client = ApiClient()
