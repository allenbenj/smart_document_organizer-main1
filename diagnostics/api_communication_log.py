"""
API Communication Logger - Track all GUI ↔ Backend requests/responses

Logs every API call with timing, status, errors for debugging connectivity issues.
Logs are written to: logs/api_communication_{timestamp}.log
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class APICommunicationLogger:
    """Detailed logging of all API requests and responses."""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"api_communication_{timestamp}.log"
        
        # Create logger
        self.logger = logging.getLogger("API_COMM")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()
        
        # File handler - all requests
        file_handler = logging.FileHandler(self.log_file, mode='w', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-7s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S.%f'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Console handler - errors only
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.ERROR)
        console_formatter = logging.Formatter('[API] %(levelname)s: %(message)s')
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # Statistics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_time_ms = 0.0
        
        self.logger.info("=" * 100)
        self.logger.info("API COMMUNICATION LOG - START")
        self.logger.info("=" * 100)
        
    def log_request(
        self, 
        method: str, 
        url: str, 
        headers: Optional[Dict] = None,
        payload: Optional[Any] = None,
        request_id: Optional[str] = None
    ) -> str:
        """Log outgoing API request."""
        if request_id is None:
            request_id = f"req_{self.total_requests + 1:05d}"
            
        self.total_requests += 1
        
        self.logger.info(f"→ REQUEST [{request_id}]")
        self.logger.info(f"  Method: {method}")
        self.logger.info(f"  URL: {url}")
        
        if headers:
            # Sanitize sensitive headers
            safe_headers = {k: v for k, v in headers.items() if k.lower() not in ['authorization', 'api-key']}
            if safe_headers:
                self.logger.debug(f"  Headers: {safe_headers}")
                
        if payload:
            # Try to pretty-print JSON, truncate if too long
            try:
                payload_str = json.dumps(payload, indent=2)
                if len(payload_str) > 1000:
                    payload_str = payload_str[:1000] + "\n  ... (truncated)"
                self.logger.debug(f"  Payload:\n{payload_str}")
            except:
                self.logger.debug(f"  Payload: {str(payload)[:500]}")
                
        return request_id
        
    def log_response(
        self,
        request_id: str,
        status_code: int,
        response_time_ms: float,
        response_body: Optional[Any] = None,
        error: Optional[Exception] = None
    ):
        """Log API response."""
        success = 200 <= status_code < 300
        
        if success:
            self.successful_requests += 1
            level = logging.INFO
            marker = "✓"
        else:
            self.failed_requests += 1
            level = logging.ERROR
            marker = "✗"
            
        self.total_time_ms += response_time_ms
        
        self.logger.log(level, f"{marker} RESPONSE [{request_id}]")
        self.logger.log(level, f"  Status: {status_code}")
        self.logger.log(level, f"  Time: {response_time_ms:.2f}ms")
        
        if error:
            self.logger.error(f"  Error: {error}")
            self.logger.error(f"  Type: {type(error).__name__}")
        elif response_body:
            # Try to pretty-print response
            try:
                if isinstance(response_body, dict):
                    response_str = json.dumps(response_body, indent=2)
                else:
                    response_str = str(response_body)
                    
                if len(response_str) > 1000:
                    response_str = response_str[:1000] + "\n  ... (truncated)"
                self.logger.debug(f"  Response:\n{response_str}")
            except:
                self.logger.debug(f"  Response: {str(response_body)[:500]}")
                
    def log_connection_error(self, request_id: str, url: str, error: Exception):
        """Log connection failures."""
        self.failed_requests += 1
        self.logger.error(f"✗ CONNECTION FAILED [{request_id}]")
        self.logger.error(f"  URL: {url}")
        self.logger.error(f"  Error: {error}")
        self.logger.error(f"  Type: {type(error).__name__}")
        
    def log_timeout(self, request_id: str, url: str, timeout_s: float):
        """Log request timeout."""
        self.failed_requests += 1
        self.logger.error(f"✗ TIMEOUT [{request_id}]")
        self.logger.error(f"  URL: {url}")
        self.logger.error(f"  Timeout: {timeout_s}s")
        
    def get_statistics(self) -> Dict[str, Any]:
        """Get communication statistics."""
        avg_time_ms = self.total_time_ms / self.total_requests if self.total_requests > 0 else 0
        success_rate = (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0
        
        return {
            "total_requests": self.total_requests,
            "successful": self.successful_requests,
            "failed": self.failed_requests,
            "success_rate_pct": round(success_rate, 1),
            "avg_response_time_ms": round(avg_time_ms, 2),
            "total_time_ms": round(self.total_time_ms, 2)
        }
        
    def finalize(self):
        """Finalize logging and print summary."""
        stats = self.get_statistics()
        
        self.logger.info("=" * 100)
        self.logger.info("API COMMUNICATION SUMMARY")
        self.logger.info("=" * 100)
        self.logger.info(f"Total Requests: {stats['total_requests']}")
        self.logger.info(f"Successful: {stats['successful']}")
        self.logger.info(f"Failed: {stats['failed']}")
        self.logger.info(f"Success Rate: {stats['success_rate_pct']}%")
        self.logger.info(f"Avg Response Time: {stats['avg_response_time_ms']}ms")
        self.logger.info(f"Total Time: {stats['total_time_ms']}ms")
        self.logger.info("=" * 100)
        self.logger.info(f"Full log: {self.log_file}")
        self.logger.info("=" * 100)


# Global instance
_api_logger: Optional[APICommunicationLogger] = None


def get_api_logger() -> APICommunicationLogger:
    """Get or create global API communication logger."""
    global _api_logger
    if _api_logger is None:
        _api_logger = APICommunicationLogger()
    return _api_logger


def log_api_call(method: str, url: str, **kwargs):
    """Convenience wrapper for API logging."""
    return get_api_logger().log_request(method, url, **kwargs)
