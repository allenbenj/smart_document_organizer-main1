"""
Backend Startup Diagnostic Logger - Detailed FastAPI/Uvicorn startup tracking

Logs every step of backend initialization to help diagnose startup failures.
Logs are written to: logs/backend_startup_{timestamp}.log
"""

import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class BackendStartupLogger:
    """Detailed startup logger for FastAPI backend with rich diagnostics."""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"backend_startup_{timestamp}.log"
        
        # Create logger
        self.logger = logging.getLogger("BACKEND_STARTUP")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()
        
        # File handler - detailed
        file_handler = logging.FileHandler(self.log_file, mode='w', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(funcName)-25s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Console handler - important only
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '[BACKEND] %(levelname)-8s | %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # Startup metrics
        self.start_time = datetime.now(timezone.utc)
        self.steps = []
        self.errors = []
        self.agents_loaded = []
        self.routes_registered = []
        
        self.logger.info("=" * 90)
        self.logger.info("BACKEND STARTUP DIAGNOSTICS - BEGIN")
        self.logger.info("=" * 90)
        self.log_environment()
        
    def log_environment(self):
        """Log environment information."""
        self.logger.info("ENVIRONMENT:")
        self.logger.info(f"  Python: {sys.version}")
        self.logger.info(f"  Platform: {sys.platform}")
        self.logger.info(f"  CWD: {os.getcwd()}")
        self.logger.info(f"  Script: {sys.argv[0] if sys.argv else 'N/A'}")
        self.logger.info(f"  Log File: {self.log_file}")
        
        # Log key environment variables
        env_vars = [
            "API_KEY", "STRICT_PRODUCTION_STARTUP", "REQUIRED_PRODUCTION_AGENTS",
            "RATE_LIMIT_REQUESTS_PER_MINUTE", "BACKEND_HEALTH_URL"
        ]
        self.logger.info("  Environment Variables:")
        for var in env_vars:
            value = os.getenv(var, "NOT SET")
            # Mask sensitive values
            if var == "API_KEY" and value != "NOT SET":
                value = "***" + value[-4:] if len(value) > 4 else "***"
            self.logger.info(f"    {var}: {value}")
        
    def step(self, step_name: str, details: Optional[str] = None):
        """Log a startup step."""
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        step_info = {
            "name": step_name,
            "elapsed_s": elapsed,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.steps.append(step_info)
        
        msg = f"STEP [{elapsed:7.2f}s]: {step_name}"
        if details:
            msg += f" | {details}"
        self.logger.info(msg)
        
    def success(self, message: str):
        """Log successful operation."""
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        self.logger.info(f"✓ [{elapsed:7.2f}s]: {message}")
        
    def warning(self, message: str, exc: Optional[Exception] = None):
        """Log warning."""
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        self.logger.warning(f"⚠ [{elapsed:7.2f}s]: {message}")
        if exc:
            self.logger.warning(f"  Exception: {exc}")
            self.logger.debug(traceback.format_exc())
            
    def error(self, message: str, exc: Optional[Exception] = None, fatal: bool = False):
        """Log error."""
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        error_info = {
            "message": message,
            "elapsed_s": elapsed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fatal": fatal,
            "exception": str(exc) if exc else None
        }
        self.errors.append(error_info)
        
        level_str = "FATAL" if fatal else "ERROR"
        self.logger.error(f"✗ [{elapsed:7.2f}s] {level_str}: {message}")
        
        if exc:
            self.logger.error(f"  Exception: {exc}")
            self.logger.error(f"  Type: {type(exc).__name__}")
            self.logger.debug("Full traceback:")
            self.logger.debug(traceback.format_exc())
            
    def debug(self, message: str, data: Any = None):
        """Log debug information."""
        self.logger.debug(f"DEBUG: {message}")
        if data is not None:
            self.logger.debug(f"  Data: {data}")
            
    def agent_loaded(self, agent_name: str, success: bool, load_time_s: Optional[float] = None, exc: Optional[Exception] = None):
        """Log agent loading."""
        self.agents_loaded.append({
            "name": agent_name,
            "success": success,
            "load_time_s": load_time_s
        })
        
        if success:
            time_str = f" ({load_time_s:.2f}s)" if load_time_s else ""
            self.success(f"Agent loaded: {agent_name}{time_str}")
        else:
            self.error(f"Agent FAILED to load: {agent_name}", exc)
            
    def route_registered(self, router_name: str, prefix: str, endpoint_count: int):
        """Log route registration."""
        self.routes_registered.append({
            "router": router_name,
            "prefix": prefix,
            "endpoints": endpoint_count
        })
        self.logger.info(f"  ✓ Registered router: {router_name} -> {prefix} ({endpoint_count} endpoints)")
        
    def database_check(self, db_path: str, exists: bool, size_mb: Optional[float] = None):
        """Log database status."""
        if exists:
            size_str = f" ({size_mb:.2f} MB)" if size_mb else ""
            self.success(f"Database found: {db_path}{size_str}")
        else:
            self.warning(f"Database not found (will create): {db_path}")
            
    def model_loaded(self, model_name: str, model_type: str, load_time_s: float):
        """Log ML model loading."""
        self.success(f"Model loaded: {model_type}/{model_name} ({load_time_s:.2f}s)")
        
    def middleware_added(self, middleware_name: str):
        """Log middleware addition."""
        self.logger.info(f"  ✓ Middleware: {middleware_name}")
        
    def finalize(self, success: bool, server_url: Optional[str] = None):
        """Finalize startup logging."""
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        
        self.logger.info("=" * 90)
        if success:
            self.logger.info(f"BACKEND STARTUP COMPLETE - {elapsed:.2f}s")
            if server_url:
                self.logger.info(f"Server running at: {server_url}")
        else:
            self.logger.error(f"BACKEND STARTUP FAILED - {elapsed:.2f}s")
            
        self.logger.info(f"Total Steps: {len(self.steps)}")
        self.logger.info(f"Agents Loaded: {len([a for a in self.agents_loaded if a['success']])}/{len(self.agents_loaded)}")
        self.logger.info(f"Routes Registered: {len(self.routes_registered)}")
        self.logger.info(f"Total Errors: {len(self.errors)}")
        
        if self.errors:
            self.logger.error("ERRORS SUMMARY:")
            for i, err in enumerate(self.errors, 1):
                fatal_marker = " [FATAL]" if err.get("fatal") else ""
                self.logger.error(f"  {i}. {err['message']}{fatal_marker}")
                if err.get("exception"):
                    self.logger.error(f"     → {err['exception']}")
                    
        if self.agents_loaded:
            failed_agents = [a for a in self.agents_loaded if not a['success']]
            if failed_agents:
                self.logger.warning("FAILED AGENTS:")
                for agent in failed_agents:
                    self.logger.warning(f"  - {agent['name']}")
                    
        self.logger.info("=" * 90)
        self.logger.info(f"Full log: {self.log_file}")
        self.logger.info("=" * 90)
        
        return {
            "success": success,
            "elapsed_s": elapsed,
            "steps": len(self.steps),
            "agents_loaded": len([a for a in self.agents_loaded if a['success']]),
            "total_agents": len(self.agents_loaded),
            "routes": len(self.routes_registered),
            "errors": len(self.errors),
            "log_file": str(self.log_file),
            "server_url": server_url
        }


# Global instance
_backend_logger: Optional[BackendStartupLogger] = None


def get_backend_logger() -> BackendStartupLogger:
    """Get or create global backend startup logger."""
    global _backend_logger
    if _backend_logger is None:
        _backend_logger = BackendStartupLogger()
    return _backend_logger


def log_step(step_name: str, details: Optional[str] = None):
    """Convenience function to log step."""
    get_backend_logger().step(step_name, details)


def log_error(message: str, exc: Optional[Exception] = None, fatal: bool = False):
    """Convenience function to log error."""
    get_backend_logger().error(message, exc, fatal)


def log_success(message: str):
    """Convenience function to log success."""
    get_backend_logger().success(message)
