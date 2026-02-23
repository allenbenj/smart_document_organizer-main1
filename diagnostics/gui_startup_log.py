"""
GUI Startup Diagnostic Logger - Detailed startup tracking for troubleshooting

This module logs every step of GUI initialization to help diagnose startup failures.
Logs are written to: logs/gui_startup_{timestamp}.log
"""

import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


class GUIStartupLogger:
    """Detailed startup logger for GUI with rich diagnostics."""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"gui_startup_{timestamp}.log"
        
        # Create logger
        self.logger = logging.getLogger("GUI_STARTUP")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()
        
        # File handler - detailed
        file_handler = logging.FileHandler(self.log_file, mode='w', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(funcName)-20s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Console handler - important only
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '[GUI] %(levelname)-8s | %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # Startup metrics
        self.start_time = datetime.now(timezone.utc)
        self.steps = []
        self.errors = []
        
        self.logger.info("=" * 80)
        self.logger.info("GUI STARTUP DIAGNOSTICS - BEGIN")
        self.logger.info("=" * 80)
        self.log_environment()
        
    def log_environment(self):
        """Log environment information."""
        self.logger.info("ENVIRONMENT:")
        self.logger.info(f"  Python: {sys.version}")
        self.logger.info(f"  Platform: {sys.platform}")
        self.logger.info(f"  CWD: {os.getcwd()}")
        self.logger.info(f"  Script: {sys.argv[0] if sys.argv else 'N/A'}")
        self.logger.info(f"  Log File: {self.log_file}")
        
    def step(self, step_name: str, details: Optional[str] = None):
        """Log a startup step."""
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        step_info = {
            "name": step_name,
            "elapsed_s": elapsed,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.steps.append(step_info)
        
        msg = f"STEP [{elapsed:6.2f}s]: {step_name}"
        if details:
            msg += f" | {details}"
        self.logger.info(msg)
        
    def success(self, message: str):
        """Log successful operation."""
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        self.logger.info(f"✓ [{elapsed:6.2f}s]: {message}")
        
    def warning(self, message: str, exc: Optional[Exception] = None):
        """Log warning."""
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        self.logger.warning(f"⚠ [{elapsed:6.2f}s]: {message}")
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
        self.logger.error(f"✗ [{elapsed:6.2f}s] {level_str}: {message}")
        
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
            
    def module_import(self, module_name: str, success: bool, exc: Optional[Exception] = None):
        """Log module import attempt."""
        if success:
            self.logger.debug(f"✓ Imported: {module_name}")
        else:
            self.error(f"Failed to import: {module_name}", exc)
            
    def component_init(self, component_name: str, success: bool, exc: Optional[Exception] = None):
        """Log component initialization."""
        if success:
            self.success(f"Initialized: {component_name}")
        else:
            self.error(f"Failed to initialize: {component_name}", exc)
            
    def backend_check(self, url: str, healthy: bool, response_time_ms: Optional[float] = None):
        """Log backend health check."""
        if healthy:
            msg = f"Backend HEALTHY at {url}"
            if response_time_ms:
                msg += f" ({response_time_ms:.1f}ms)"
            self.success(msg)
        else:
            self.error(f"Backend UNAVAILABLE at {url}")
            
    def tab_creation(self, tab_name: str, success: bool, exc: Optional[Exception] = None):
        """Log tab creation."""
        if success:
            self.logger.info(f"  ✓ Tab created: {tab_name}")
        else:
            self.error(f"  ✗ Tab FAILED: {tab_name}", exc)
            
    def finalize(self, success: bool):
        """Finalize startup logging."""
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        
        self.logger.info("=" * 80)
        if success:
            self.logger.info(f"GUI STARTUP COMPLETE - {elapsed:.2f}s")
        else:
            self.logger.error(f"GUI STARTUP FAILED - {elapsed:.2f}s")
            
        self.logger.info(f"Total Steps: {len(self.steps)}")
        self.logger.info(f"Total Errors: {len(self.errors)}")
        
        if self.errors:
            self.logger.error("ERRORS SUMMARY:")
            for i, err in enumerate(self.errors, 1):
                fatal_marker = " [FATAL]" if err.get("fatal") else ""
                self.logger.error(f"  {i}. {err['message']}{fatal_marker}")
                if err.get("exception"):
                    self.logger.error(f"     → {err['exception']}")
                    
        self.logger.info("=" * 80)
        self.logger.info(f"Full log: {self.log_file}")
        self.logger.info("=" * 80)
        
        return {
            "success": success,
            "elapsed_s": elapsed,
            "steps": len(self.steps),
            "errors": len(self.errors),
            "log_file": str(self.log_file)
        }


# Global instance
_startup_logger: Optional[GUIStartupLogger] = None


def get_startup_logger() -> GUIStartupLogger:
    """Get or create global startup logger."""
    global _startup_logger
    if _startup_logger is None:
        _startup_logger = GUIStartupLogger()
    return _startup_logger


def log_step(step_name: str, details: Optional[str] = None):
    """Convenience function to log step."""
    get_startup_logger().step(step_name, details)


def log_error(message: str, exc: Optional[Exception] = None, fatal: bool = False):
    """Convenience function to log error."""
    get_startup_logger().error(message, exc, fatal)


def log_success(message: str):
    """Convenience function to log success."""
    get_startup_logger().success(message)
