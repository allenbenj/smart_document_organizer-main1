#!/usr/bin/env python3
"""
File Index Initialization Script

Initialize the file index database for tracking application source files.
This creates a comprehensive database for understanding the codebase structure.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.db.file_index_manager import FileIndexManager


def main():
    """Initialize the file index."""
    print("=" * 80)
    print("FILE INDEX INITIALIZATION")
    print("=" * 80)
    print("\nThis will create a database to track and analyze all source files")
    print("in this application. This is for development purposes only.")
    print("\nDatabase: databases/file_index.db")
    print("=" * 80)
    
    # Confirm initialization
    response = input("\nProceed with initialization? [Y/n]: ").strip().lower()
    if response and response not in ('y', 'yes'):
        print("Initialization cancelled.")
        return 0
    
    try:
        # Create manager (this also initializes the database)
        print("\n📦 Creating database...")
        manager = FileIndexManager(
            db_path="databases/file_index.db",
            project_root="."
        )
        
        # Perform initial scan
        print("\n🔍 Scanning files...")
        stats = manager.scan_files(incremental=False)
        
        # Show results
        print("\n" + "=" * 80)
        print("INITIALIZATION COMPLETE")
        print("=" * 80)
        
        print(f"\n✓ Files Indexed: {stats['added']}")
        print(f"✓ Files Skipped: {stats['skipped']}")
        
        # Show statistics
        print("\n📊 Index Statistics:")
        overall_stats = manager.get_statistics()
        print(f"   Total Files: {overall_stats['total_files']}")
        print(f"   Total Lines: {overall_stats['total_lines_of_code']:,}")
        
        if overall_stats['by_category']:
            print(f"\n📁 Top Categories:")
            for cat in overall_stats['by_category'][:5]:
                print(f"   {cat['file_category']}: {cat['count']} files")
        
        print("\n" + "=" * 80)
        print("NEXT STEPS")
        print("=" * 80)
        print("\n1. Inspect the index:")
        print("   python tools/db/file_index_inspector.py --overview")
        print("\n2. Search for files:")
        print("   python tools/db/file_index_inspector.py --search 'agent'")
        print("\n3. View file details:")
        print("   python tools/db/file_index_inspector.py --file 'path/to/file.py'")
        print("\n4. Export to JSON:")
        print("   python tools/db/file_index_inspector.py --export file_index.json")
        print("\n5. Rescan files:")
        print("   python tools/db/file_index_manager.py")
        print("\n" + "=" * 80)
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
