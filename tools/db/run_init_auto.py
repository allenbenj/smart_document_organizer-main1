#!/usr/bin/env python3
"""Temporary script to initialize file index without interactive prompt."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.db.file_index_manager import FileIndexManager

def main():
    print("=" * 80)
    print("FILE INDEX INITIALIZATION (AUTO-MODE)")
    print("=" * 80)
    
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
        
        print("\n✓ Initialization successful!")
        return 0
        
    except Exception as e:
        print(f"\n❌ Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())
