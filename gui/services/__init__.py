"""
GUI Services - API client and data management for the Legal AI GUI

This module provides centralized API communication and data handling
to keep the GUI components clean and focused on UI logic.
"""

import os
import time
from typing import Any, Dict, Optional

try:
    import requests  # noqa: E402
    from requests.adapters import HTTPAdapter  # noqa: E402
    from urllib3.util.retry import Retry  # noqa: E402
except ImportError:
    requests = None
    HTTPAdapter = None
    Retry = None


class ApiClient:
    """Centralized API client for GUI operations with robust error handling."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 30.0, max_retries: int = 3):
        resolved = (base_url or os.getenv("SMART_DOC_API_BASE_URL") or "http://127.0.0.1:8000").strip()
        self.base_url = resolved.rstrip("/")
        self.default_timeout = timeout
        self.session = None

        if requests and HTTPAdapter and Retry:
            self.session = requests.Session()
            # Configure retry strategy for transient failures
            retry_strategy = Retry(
                total=max_retries,
                status_forcelist=[429, 500, 502, 503, 504],  # Retry on these status codes
                allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],  # urllib3 v2+
                backoff_factor=1,  # Exponential backoff: 1, 2, 4 seconds
                raise_on_status=False  # Don't raise immediately on bad status
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)

    @property
    def api_base_url(self) -> str:
        """Return API root URL (base + /api)."""
        return f"{self.base_url}/api"

    def api_url(self, path: str) -> str:
        """Build full URL from either '/api/..' or '/..' path."""
        if not path:
            return self.base_url
        if path.startswith("/api/"):
            return f"{self.base_url}{path}"
        if path.startswith("/"):
            return f"{self.api_base_url}{path}"
        return f"{self.api_base_url}/{path}"


    def _make_request(self, method: str, endpoint: str, timeout: Optional[float] = None, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with robust error handling and retries."""
        if not self.session:
            raise RuntimeError("requests library not available - cannot make API calls")

        url = self.api_url(endpoint)
        actual_timeout = timeout if timeout is not None else self.default_timeout

        # Ensure timeout is set in kwargs
        kwargs.setdefault('timeout', actual_timeout)

        print(f"[API] {method} {url} (timeout={actual_timeout}s)...")
        try:
            start_time = time.time()
            response = self.session.request(method, url, **kwargs)
            duration = time.time() - start_time
            print(f"[API] Response {response.status_code} in {duration:.2f}s")
            
            response.raise_for_status()
            data = response.json() if response.content else {}
            # print(f"[API] Parsed payload bytes: {len(response.content)}")
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
        return self._make_request("GET", "/api/health", timeout=10.0)

    def analyze_semantic(self, text: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Perform semantic analysis."""
        data = {"text": text, "options": options or {}}
        return self._make_request("POST", "/api/analysis/semantic", timeout=30.0, json=data)

    def extract_entities(self, text: str, entity_types: Optional[list] = None, extraction_type: str = "ner") -> Dict[str, Any]:
        """Extract entities from text."""
        data = {"text": text, "options": {}, "extraction_type": extraction_type}
        if entity_types:
            data["options"]["entity_types"] = entity_types
        return self._make_request("POST", "/api/extraction/run", timeout=30.0, json=data)

    def process_document(self, file_path: str) -> Dict[str, Any]:
        """Process document file."""
        import mimetypes  # noqa: E402
        import os  # noqa: E402

        mt, _ = mimetypes.guess_type(file_path)
        with open(file_path, "rb") as f:
            files = {
                "file": (
                    os.path.basename(file_path),
                    f,
                    mt or "application/octet-stream",
                )
            }
            return self._make_request("POST", "/api/agents/process-document", timeout=120.0, files=files)

    def classify_text(self, text: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Classify text using the classification agent."""
        data = {"text": text, "options": options or {}}
        return self._make_request("POST", "/api/classification/run", timeout=30.0, json=data)

    def get_expert_prompt(self, agent_name: str, task_type: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get expert prompt for a task."""
        data = {"agent_name": agent_name, "task_type": task_type, "task_data": task_data}
        return self._make_request("POST", "/api/experts/prompt", timeout=15.0, json=data)

    def get_ontology_entities(self) -> Dict[str, Any]:
        """Get ontology entities for KG."""
        return self._make_request("GET", "/api/ontology/entities", timeout=10.0)

    def get_knowledge_entities(self) -> Dict[str, Any]:
        """Get knowledge entities."""
        return self._make_request("GET", "/api/knowledge/entities", timeout=10.0)

    def add_knowledge_entity(self, name: str, entity_type: str) -> Dict[str, Any]:
        """Add a knowledge entity."""
        data = {"name": name, "entity_type": entity_type}
        return self._make_request("POST", "/api/knowledge/entities", timeout=10.0, json=data)

    def analyze_legal_kg(self, text: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Perform legal reasoning with knowledge graph."""
        data = {"text": text, "options": (options or {}) | {"analysis_type": "KG"}}
        return self._make_request("POST", "/api/agents/legal", timeout=30.0, json=data)

    def analyze_legal_reasoning(self, text: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Perform legal reasoning analysis."""
        data = {"text": text, "options": options or {}}
        return self._make_request("POST", "/api/reasoning/legal", timeout=30.0, json=data)

    def import_triples(self, triples: list, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Import knowledge triples."""
        data = (options or {}) | {"triples": triples}
        return self._make_request("POST", "/api/knowledge/import_triples", timeout=30.0, json=data)

    def get_knowledge_proposals(self) -> Dict[str, Any]:
        """Get knowledge proposals."""
        return self._make_request("GET", "/api/knowledge/proposals", timeout=10.0)

    def approve_proposal(self, proposal_id: int) -> Dict[str, Any]:
        """Approve a knowledge proposal."""
        data = {"id": proposal_id}
        return self._make_request("POST", "/api/knowledge/proposals/approve", timeout=10.0, json=data)

    def reject_proposal(self, proposal_id: int) -> Dict[str, Any]:
        """Reject a knowledge proposal."""
        data = {"id": proposal_id}
        return self._make_request("POST", "/api/knowledge/proposals/reject", timeout=10.0, json=data)

    def get_pipeline_presets(self) -> Dict[str, Any]:
        """Get pipeline presets."""
        return self._make_request("GET", "/api/pipeline/presets", timeout=10.0)

    def run_pipeline(self, preset: Dict[str, Any], path: Optional[str] = None) -> Dict[str, Any]:
        """Run a pipeline."""
        data = {
            "steps": preset.get("steps", []),
            "context": {"path": path} if path else preset.get("context", {})
        }
        return self._make_request("POST", "/api/pipeline/run", timeout=120.0, json=data)

    def get_vector_status(self) -> Dict[str, Any]:
        """Get vector database status."""
        return self._make_request("GET", "/api/vector", timeout=5.0)

    def embed_texts(self, texts: list, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Embed texts."""
        data = {"texts": texts, "options": options or {}}
        return self._make_request("POST", "/api/agents/embed", timeout=30.0, json=data)

    def vector_search(self, embedding: list, top_k: int = 5) -> Dict[str, Any]:
        """Search vectors."""
        data = {"embedding": embedding, "top_k": top_k}
        return self._make_request("POST", "/api/vector/search", timeout=15.0, json=data)

    def process_documents_batch(self, file_paths: list, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Process multiple documents."""
        import mimetypes  # noqa: E402
        import os  # noqa: E402

        # FastAPI expects all files under the same field name "files"
        # requests needs a list of (field_name, (filename, fh, content_type)) tuples
        file_handles = []
        files_list = []
        for file_path in file_paths:
            mt, _ = mimetypes.guess_type(file_path)
            fh = open(file_path, "rb")
            file_handles.append(fh)
            files_list.append(
                ("files", (os.path.basename(file_path), fh, mt or "application/octet-stream"))
            )

        try:
            result = self._make_request(
                "POST", "/api/agents/process-documents",
                timeout=300.0, files=files_list,
                data={"options": options} if options else None,
            )
            return result
        finally:
            for fh in file_handles:
                fh.close()

    def import_text_to_knowledge(self, text: str) -> Dict[str, Any]:
        """Import text to knowledge base."""
        data = {"text": text}
        return self._make_request("POST", "/api/knowledge/import-text", timeout=120.0, json=data)

    def fetch_embeddings(self, text: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Get embeddings for text."""
        data = {"text": text, "options": options or {}}
        return self._make_request("POST", "/api/embeddings/", timeout=30.0, json=data)

    def run_embedding_operation(self, text: str, model_name: str, operation: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Run a specific embedding operation."""
        data = {"text": text, "model_name": model_name, "operation": operation, "options": options or {}}
        return self._make_request("POST", "/api/embeddings/run_operation", timeout=30.0, json=data)

    def organize_document(self, text: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Organize document content."""
        data = {"text": text, "options": options or {}}
        return self._make_request("POST", "/api/agents/organize", timeout=30.0, json=data)

    def index_to_vector(self, text: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Index text to vector database."""
        data = {"text": text, "options": options or {}}
        return self._make_request("POST", "/api/vector/index", timeout=30.0, json=data)


# Global API client instance
api_client = ApiClient()
