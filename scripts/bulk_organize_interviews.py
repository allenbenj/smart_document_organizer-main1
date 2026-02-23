
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mem_db.database import get_database_manager
from services.organization_service import OrganizationService

def main():
    db = get_database_manager()
    svc = OrganizationService(db)
    
    root_path = "/mnt/e/Organization_Folder/02_Working_Folder/02_Analysis/08_Interviews"
    
    print(f"Starting bulk organization for: {root_path}")
    
    # 1. Generate Proposals (this includes seeding index)
    print("Generating proposals...")
    gen_result = svc.generate_proposals(root_prefix=root_path, limit=500)
    created = gen_result.get("created", 0)
    print(f"Created {created} proposals.")
    
    if created == 0:
        print("No proposals created. Checking for existing ones...")
        # Check if they are already proposed
        existing = svc.list_proposals(root_prefix=root_path, status="proposed")
        items = existing.get("items", [])
        if not items:
            print("No proposed items found for this scope.")
            return
        print(f"Found {len(items)} existing proposals.")
    else:
        items = gen_result.get("items", [])

    # 2. Bulk Approve
    print("Approving proposals...")
    approved_count = 0
    for p in items:
        pid = p.get("id")
        if pid:
            res = svc.approve_proposal(pid)
            if res.get("success"):
                approved_count += 1
    
    print(f"Approved {approved_count} proposals.")

    # 3. Apply Approved (Move files)
    print("Applying approved moves (Live)...")
    apply_result = svc.apply_approved(root_prefix=root_path, dry_run=False, limit=500)
    
    applied = apply_result.get("applied", 0)
    failed = apply_result.get("failed", 0)
    
    print(f"Bulk Phase Complete: {applied} files moved, {failed} failed.")
    
    if failed > 0:
        for r in apply_result.get("results", []):
            if not r.get("ok"):
                print(f"Error moving {r.get('from')}: {r.get('error')}")

if __name__ == "__main__":
    main()
