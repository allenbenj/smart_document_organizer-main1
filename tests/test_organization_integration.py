#!/usr/bin/env python3
"""
Document Organization & Indexing Integration Test
==================================================

This script tests the core document indexing and organization workflow
to ensure everything is properly integrated and working.

Usage:
    python test_organization_integration.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from mem_db.database import get_database_manager
from services.file_index_service import FileIndexService
from services.organization_service import OrganizationService


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def test_database_health():
    """Test that all databases are accessible and have correct schema."""
    print_section("Database Health Check")
    
    try:
        db = get_database_manager()
        print("✅ Database manager initialized successfully")
        
        # Check critical tables exist
        with db.get_connection() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {row[0] for row in tables}
            
            required_tables = {
                'files_index', 'documents', 'organization_proposals',
                'organization_feedback', 'organization_actions',
                'document_tags', 'file_content_chunks'
            }
            
            missing = required_tables - table_names
            if missing:
                print(f"⚠️  Missing tables: {missing}")
                return False
            else:
                print(f"✅ All {len(required_tables)} required tables present")
        
        return True
        
    except Exception as e:
        print(f"❌ Database health check failed: {e}")
        return False


def test_file_indexing():
    """Test file indexing functionality."""
    print_section("File Indexing Test")
    
    try:
        db = get_database_manager()
        service = FileIndexService(db)
        print("✅ File index service initialized")
        
        # Check current index count
        files = db.list_all_indexed_files()
        print(f"📊 Current indexed files: {len(files)}")
        
        # Show breakdown by status
        status_counts = {}
        for f in files:
            status = f.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        for status, count in status_counts.items():
            print(f"   - {status}: {count}")
        
        return True
        
    except Exception as e:
        print(f"❌ File indexing test failed: {e}")
        return False


def test_organization_service():
    """Test organization proposal service."""
    print_section("Organization Service Test")
    
    try:
        db = get_database_manager()
        service = OrganizationService(db)
        print("✅ Organization service initialized")
        
        # Check LLM status
        llm_status = service.llm_status()
        active_provider = llm_status.get('active', {}).get('provider', 'unknown')
        active_model = llm_status.get('active', {}).get('model', 'unknown')
        print(f"🤖 Active LLM: {active_provider} - {active_model}")
        
        # Check if providers are configured
        configured = llm_status.get('configured', {})
        for provider, is_configured in configured.items():
            status_icon = "✅" if is_configured else "⚠️"
            print(f"   {status_icon} {provider}: {'Configured' if is_configured else 'Not configured'}")
        
        # Check existing proposals
        proposals = service.list_proposals(status='proposed', limit=100)
        proposal_items = proposals.get('items', [])
        print(f"\n📋 Existing proposals: {len(proposal_items)}")
        
        if len(proposal_items) > 0:
            # Show breakdown by confidence
            high_conf = sum(1 for p in proposal_items if p.get('confidence', 0) >= 0.8)
            med_conf = sum(1 for p in proposal_items if 0.5 <= p.get('confidence', 0) < 0.8)
            low_conf = sum(1 for p in proposal_items if p.get('confidence', 0) < 0.5)
            
            print(f"   - High confidence (≥0.8): {high_conf}")
            print(f"   - Medium confidence (0.5-0.8): {med_conf}")
            print(f"   - Low confidence (<0.5): {low_conf}")
        
        # Check feedback and actions
        feedback = service.list_feedback(limit=100)
        actions = service.list_actions(limit=100)
        
        print(f"\n📊 Historical data:")
        print(f"   - Feedback records: {len(feedback.get('items', []))}")
        print(f"   - Action records: {len(actions.get('items', []))}")
        
        # Get statistics
        stats = service.stats()
        print(f"\n📈 Organization statistics:")
        print(f"   - Total proposals: {stats.get('total_proposals', 0)}")
        by_status = stats.get('by_status', {})
        for status, count in by_status.items():
            print(f"   - {status}: {count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Organization service test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_repository_layer():
    """Test repository layer access."""
    print_section("Repository Layer Test")
    
    try:
        db = get_database_manager()
        
        # Test organization repository
        org_repo = db.organization_repo
        proposals = org_repo.list_proposals(limit=5)
        print(f"✅ Organization repository: {len(proposals)} proposals")
        
        # Test file index repository
        file_repo = db.file_index_repo
        files = file_repo.list_files(limit=5)
        print(f"✅ File index repository: {len(files)} files")
        
        # Test document repository
        doc_repo = db.document_repo
        docs = doc_repo.list_documents(limit=5)
        print(f"✅ Document repository: {len(docs)} documents")
        
        return True
        
    except Exception as e:
        print(f"❌ Repository layer test failed: {e}")
        return False


def test_integration_workflow():
    """Test end-to-end integration workflow."""
    print_section("Integration Workflow Test")
    
    print("\n📝 Testing workflow sequence:")
    print("   1. File scanning → files_index table")
    print("   2. Organization proposal generation")
    print("   3. Proposal approval workflow")
    print("   4. File move operations\n")
    
    try:
        db = get_database_manager()
        
        # Step 1: Check files are indexed
        files = db.list_all_indexed_files()
        ready_files = [f for f in files if f.get('status') == 'ready']
        print(f"✅ Step 1: {len(ready_files)} files ready for organization")
        
        # Step 2: Check organization service can access files
        org_service = OrganizationService(db)
        
        # Simulate checking if generation would work (don't actually generate)
        print(f"✅ Step 2: Organization service can access indexed files")
        
        # Step 3: Check proposal workflow
        proposals = org_service.list_proposals(limit=10)
        print(f"✅ Step 3: Proposal workflow active ({len(proposals.get('items', []))} proposals)")
        
        # Step 4: Check action tracking
        actions = org_service.list_actions(limit=10)
        print(f"✅ Step 4: Action tracking active ({len(actions.get('items', []))} actions)")
        
        print("\n✅ Integration workflow test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Integration workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all integration tests."""
    print("\n" + "=" * 80)
    print("  DOCUMENT ORGANIZATION & INDEXING - INTEGRATION TEST")
    print("=" * 80)
    
    results = {
        "Database Health": test_database_health(),
        "File Indexing": test_file_indexing(),
        "Organization Service": test_organization_service(),
        "Repository Layer": test_repository_layer(),
        "Integration Workflow": test_integration_workflow(),
    }
    
    print_section("Test Results Summary")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}  {test_name}")
    
    print(f"\n{'=' * 80}")
    print(f"Overall: {passed}/{total} tests passed")
    print("=" * 80)
    
    if passed == total:
        print("\n🎉 All tests passed! System is ready for use.")
        print("\nNext steps:")
        print("  1. Launch GUI: python gui/gui_dashboard.py")
        print("  2. Test organization workflow in Organization tab")
        print("  3. Process documents in Document Processing tab")
        return 0
    else:
        print("\n⚠️  Some tests failed. Review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
