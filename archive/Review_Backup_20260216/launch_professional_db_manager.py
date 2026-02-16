#!/usr/bin/env python3
"""
Professional Database Manager Launcher
=====================================

Simple launcher script for the Professional Database Management System.
Includes dependency checking and graceful error handling.
"""

import sys
import os
from pathlib import Path

def check_dependencies():
    """Check for required dependencies."""
    required_modules = ['PyQt6', 'sqlite3']
    missing = []
    
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    
    if missing:
        print(f"Missing required modules: {', '.join(missing)}")
        print("\nTo install missing dependencies:")
        for module in missing:
            if module == 'PyQt6':
                print("  pip install PyQt6")
        return False
    
    return True

def main():
    """Launch the Professional Database Manager."""
    print("Professional Database Management System")
    print("======================================")
    
    # Check dependencies
    if not check_dependencies():
        print("\nPlease install missing dependencies and try again.")
        return 1
    
    # Add current directory to path
    current_dir = Path(__file__).parent
    sys.path.insert(0, str(current_dir))
    
    try:
        # Import and run the professional database manager
        from professional_database_manager import main as run_manager
        print("Starting Professional Database Manager...")
        run_manager()
        
    except ImportError as e:
        print(f"Error importing database manager: {e}")
        return 1
    except Exception as e:
        print(f"Error starting database manager: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())