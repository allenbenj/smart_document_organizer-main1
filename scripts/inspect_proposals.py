
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mem_db.database import get_database_manager
from services.organization_service import OrganizationService

def main():
    try:
        db = get_database_manager()
        svc = OrganizationService(db)
        
        root_path = "/mnt/e/Organization_Folder/02_Working_Folder/02_Analysis/08_Interviews"
        
        print(f"Inspecting proposals for: {root_path}")
        
        # List existing proposals
        result = svc.list_proposals(root_prefix=root_path)
        items = result.get("items", [])
        
        print(f"Found {len(items)} proposals in this scope.")
        for p in items:
            print(f"- ID {p.get('id')}: {Path(p.get('current_path')).name} -> {p.get('proposed_folder')}/{p.get('proposed_filename')} ({p.get('status')})")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
