"""
DEPRECATED: This GUI dashboard has been merged into professional_manager.py.

This file is now a compatibility wrapper and will be removed in a future version.
Please run professional_manager.py directly.
"""
import sys
import os
import warnings

# Add project root to python path to ensure imports work correctly
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Issue a clear deprecation warning
warnings.warn(
    "`gui_dashboard.py` is deprecated and will be removed. "
    "Please run `professional_manager.py` instead.",
    DeprecationWarning,
    stacklevel=2,
)

print("---")
print("DEPRECATION WARNING: `gui_dashboard.py` has been merged into `professional_manager.py`.")
print("Launching the new unified dashboard...")
print("---", flush=True)

try:
    # It's better to import and run the main function from the new module
    from gui.professional_manager import main as launch_professional_manager
except ImportError as e:
    print(f"Failed to import the new dashboard: {e}", file=sys.stderr)
    print("Please ensure the project structure is correct.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    launch_professional_manager()
