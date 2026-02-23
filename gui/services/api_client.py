import requests
import os
import logging
import json
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Base URL for the backend API
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api")

class APIClient:
    """
    A simple API client for interacting with the backend services.
    Encapsulates common HTTP request patterns and error handling.
    """
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        logger.info(f"APIClient initialized with base URL: {self.base_url}")

    def _full_url(self, path: str) -> str:
        """Constructs the full URL for an API endpoint."""
        return f"{self.base_url}{path}"

    def get(self, path: str, params: Optional[Dict[str, Any]] = None, timeout: float = 10.0) -> Dict[str, Any]:
        """Sends a GET request to the API."""
        url = self._full_url(path)
        logger.info(f"[API] GET {url} (timeout={timeout}s)...")
        try:
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status() # Raise an exception for HTTP errors
            logger.info(f"[API] Response {response.status_code} in {response.elapsed.total_seconds():.2f}s")
            return response.json()
        except requests.exceptions.Timeout:
            logger.error(f"[API] Request timed out after {timeout}s for GET {url}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"[API] Request failed for GET {url}: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"[API] Failed to decode JSON response for GET {url}: {e}")
            raise

    def post(self, path: str, json: Optional[Dict[str, Any]] = None, timeout: float = 10.0) -> Dict[str, Any]:
        """Sends a POST request to the API."""
        url = self._full_url(path)
        logger.info(f"[API] POST {url} (timeout={timeout}s)...")
        try:
            response = requests.post(url, json=json, timeout=timeout)
            response.raise_for_status()
            logger.info(f"[API] Response {response.status_code} in {response.elapsed.total_seconds():.2f}s")
            return response.json()
        except requests.exceptions.Timeout:
            logger.error(f"[API] Request timed out after {timeout}s for POST {url}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"[API] Request failed for POST {url}: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"[API] Failed to decode JSON response for POST {url}: {e}")
            raise

    def get_health(self) -> Dict[str, Any]:
        """Fetches health status of the backend."""
        return self.get("/health")

    def get_ontology_entities(self) -> Dict[str, Any]:
        """Fetches ontology entities."""
        return self.get("/ontology/entities")

    def get_vector_status(self) -> Dict[str, Any]:
        """Fetches vector store status."""
        return self.get("/vector")

    def list_manager_knowledge(self, limit: int = 500, offset: int = 0) -> Dict[str, Any]:
        """Fetches curated knowledge items from the knowledge manager."""
        return self.get(f"/knowledge/manager/items", params={"limit": limit, "offset": offset})

    def list_memory_proposals(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Fetches memory proposals."""
        return self.get(f"/agents/memory/proposals", params={"limit": limit, "offset": offset})

# Create a singleton instance of the APIClient
api_client = APIClient()


def __getattr__(name: str):
    """
    Compatibility shim:
    if callers treat this module as a client object (e.g. module.method()),
    delegate to the singleton instance.
    """
    try:
        return getattr(api_client, name)
    except AttributeError as exc:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'") from exc
