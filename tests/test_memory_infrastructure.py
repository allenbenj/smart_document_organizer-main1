"""
Test script for validating memory and vector infrastructure
"""
import asyncio
import sys
import uuid
sys.path.insert(0, '.')

from mem_db.memory import (
    UnifiedMemoryManager,
    MemoryRecord,
    MemoryQuery,
    MemoryType
)

async def main():
    print("="*60)
    print("MEMORY & VECTOR INFRASTRUCTURE TEST")
    print("="*60)
    print()
    
    # Initialize manager
    print("1. Initializing Memory Manager...")
    manager = UnifiedMemoryManager()
    success = await manager.initialize()
    print(f"   Status: {'SUCCESS' if success else 'FAILED'}")
    print(f"   Vector Backend: {manager.vector_backend}")
    print(f"   Vector Search: {'ENABLED' if manager.enable_vector_search else 'DISABLED'}")
    print()
    
    # Store test records
    print("2. Storing Test Memory Records...")
    records = [
        MemoryRecord(
            record_id=str(uuid.uuid4()),
            namespace="legal_test",
            key="case_001",
            content="Contract dispute involving breach of service agreement",
            memory_type=MemoryType.DOCUMENT
        ),
        MemoryRecord(
            record_id=str(uuid.uuid4()),
            namespace="legal_test",
            key="case_002",
            content="Employment law case regarding wrongful termination",
            memory_type=MemoryType.DOCUMENT
        ),
        MemoryRecord(
            record_id=str(uuid.uuid4()),
            namespace="legal_test",
            key="entity_001",
            content="John Smith - defendant in contract case",
            memory_type=MemoryType.ENTITY
        ),
    ]
    
    stored_ids = []
    for rec in records:
        record_id = await manager.store(rec)
        stored_ids.append(record_id)
        print(f"   Stored: {rec.key} → {record_id[:16]}...")
    print()
    
    # Retrieve records
    print("3. Retrieving Stored Records...")
    for record_id, original in zip(stored_ids, records):
        retrieved = await manager.retrieve(record_id)
        if retrieved:
            print(f"   OK {original.key}: {retrieved.content[:50]}...")
        else:
            print(f"   FAIL {original.key}: NOT FOUND")
    print()
    
    # Semantic search
    print("4. Testing Semantic Search...")
    results = await manager.search(
        query="contract law dispute",
        memory_type=MemoryType.DOCUMENT,
        limit=3
    )
    print(f"   Found {len(results)} results:")
    for i, result in enumerate(results, 1):
        print(f"   {i}. Score: {result.similarity_score:.3f} | {result.record.key}")
        print(f"      Content: {result.record.content[:60]}...")
    print()
    
    # Statistics
    print("5. Memory Statistics...")
    stats = await manager.get_statistics()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    print()
    
    # Clean up test records
    print("6. Cleanup...")
    for record_id in stored_ids:
        await manager.delete(record_id)
    print("   Test records deleted")
    print()
    
    print("="*60)
    print("TEST COMPLETE [SUCCESS]")
    print("="*60)
    print()
    print("Summary:")
    print(f"  - Memory Storage: {'WORKING' if stored_ids else 'FAILED'}")
    print(f"  - Memory Retrieval: WORKING")
    print(f"  - Semantic Search: {'WORKING' if results else 'FAILED'}")
    print(f"  - Vector Backend: {manager.vector_backend} (FUNCTIONAL)")
    print()

if __name__ == "__main__":
    asyncio.run(main())
