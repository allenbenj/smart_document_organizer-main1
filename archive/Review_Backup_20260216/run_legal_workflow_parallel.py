#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parallel Legal Organization Workflow
Processes files using multiprocessing for significant speed improvements.

Uses multiple worker processes to scan, extract, and route files concurrently.
"""

import sys
import os
from pathlib import Path
from multiprocessing import Pool, Manager, cpu_count
from functools import partial
import time

# Fix Unicode encoding for Windows console
if sys.platform == 'win32':
    try:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except:
        pass

from deepseek_config import get_deepseek_config, test_deepseek_connection
from file_organizer.legal.coordinator import LegalModeCoordinator
from file_organizer.routing.plan_executor import PlanExecutor
from file_organizer.undo.undo_manager import UndoManager


def process_file_worker(file_path, legal_root, counter, total_files, lock):
    """Worker function to process a single file. Runs in separate process."""
    try:
        # Each worker gets its own coordinator instance
        coordinator = LegalModeCoordinator(legal_root)

        # Read file content
        ext = file_path.suffix.lower()
        if ext in {'.pdf', '.docx', '.xlsx', '.zip', '.jpg', '.png', '.exe', '.dll'}:
            content = f"Binary file: {file_path.name} ({file_path.stat().st_size} bytes)"
        else:
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
            except:
                content = f"Unable to read: {file_path.name}"

        # Process through legal pipeline
        result = coordinator.process_file(file_path, content, file_path.name)

        # Update progress counter
        with lock:
            counter.value += 1
            current = counter.value
            if current % 100 == 0 or current == total_files:
                print(f"\rProcessed: {current}/{total_files} ({current*100//total_files}%)", end='', flush=True)

        coordinator.close()

        return {
            'success': True,
            'file_path': str(file_path),
            'file_id': result['file_id'],
            'target_path': str(result['target_path']),
            'lifecycle_state': result['lifecycle_state'],
            'confidence': result['confidence'],
            'case_binding': result.get('case_binding'),
            'entities_extracted': result['entities_extracted']
        }

    except Exception as e:
        with lock:
            counter.value += 1
        return {
            'success': False,
            'file_path': str(file_path),
            'error': str(e)
        }


def main():
    # Configuration
    source_dir = Path("E:/Organization_Folder")
    legal_root = Path("E:/Organization_Folder")

    # Determine number of worker processes (use 75% of CPUs to avoid overload)
    num_workers = max(1, int(cpu_count() * 0.75))

    print("=" * 70)
    print("PARALLEL LEGAL FILE ORGANIZATION WORKFLOW")
    print("=" * 70)
    print(f"Source Directory: {source_dir}")
    print(f"Legal Root: {legal_root}")
    print(f"Worker Processes: {num_workers}")
    print()

    # Configure DeepSeek LLM
    print("Configuring DeepSeek LLM...")
    model_config = get_deepseek_config()

    # Test connection (optional, don't block on failure)
    if not test_deepseek_connection(model_config):
        print("⚠ DeepSeek connection failed (will use pattern-based extraction)")
    print()

    # Step 1: Scan for files
    print("[Step 1] Scanning directory for files...")
    start_scan = time.time()

    all_files = list(source_dir.rglob("*"))
    files_to_process = [f for f in all_files if f.is_file()]

    scan_time = time.time() - start_scan
    print(f"✓ Found {len(files_to_process):,} files in {scan_time:.1f}s")
    print()

    if not files_to_process:
        print("No files to process.")
        return

    # Step 2: Process files in parallel
    print(f"[Step 2] Extracting metadata using {num_workers} workers...")
    print("This will be MUCH faster than single-threaded processing.")
    print()

    start_process = time.time()

    # Create shared counter for progress tracking
    manager = Manager()
    counter = manager.Value('i', 0)
    lock = manager.Lock()

    # Create worker function with fixed arguments
    worker_func = partial(
        process_file_worker,
        legal_root=legal_root,
        counter=counter,
        total_files=len(files_to_process),
        lock=lock
    )

    # Process files in parallel
    with Pool(processes=num_workers) as pool:
        results = pool.map(worker_func, files_to_process, chunksize=10)

    print()  # New line after progress
    process_time = time.time() - start_process

    # Separate successful and failed results
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]

    print()
    print(f"✓ Processing complete in {process_time:.1f}s")
    print(f"  Successful: {len(successful):,}")
    print(f"  Failed: {len(failed):,}")
    print(f"  Speed: {len(files_to_process)/process_time:.1f} files/second")
    print()

    if failed:
        print(f"Failed files ({len(failed)}):")
        for fail in failed[:10]:
            print(f"  - {Path(fail['file_path']).name}: {fail['error']}")
        if len(failed) > 10:
            print(f"  ... and {len(failed) - 10} more")
        print()

    if not successful:
        print("No files were successfully processed. Exiting.")
        return

    # Step 3: Create organization plan
    print("[Step 3] Creating organization plan...")

    coordinator = LegalModeCoordinator(legal_root)

    plan_items = []
    for result in successful:
        file_path = Path(result['file_path'])
        file_id = result['file_id']

        status = coordinator.get_file_status(file_id)
        if not status:
            continue

        extraction_result = coordinator.get_extraction_result(file_id)
        if extraction_result:
            routing_result = coordinator.router.route(
                extraction_result=extraction_result,
                file_path=file_path,
                current_state=None
            )

            # Determine if file can be moved
            plan_status = "ALLOWED"
            blocked_reason = None

            if status['lifecycle_state'] in ['filed', 'locked']:
                plan_status = "BLOCKED"
                blocked_reason = "IMMUTABLE"
            elif routing_result.requires_user_confirmation:
                plan_status = "BLOCKED"
                blocked_reason = "REQUIRES_CONFIRMATION"

            target_path = routing_result.target_path / file_path.name

            plan_items.append({
                "file_id": file_id,
                "action": "MOVE",
                "frm": str(file_path),
                "to": str(target_path),
                "status": plan_status,
                "blocked_reason": blocked_reason,
                "target_lifecycle_state": routing_result.lifecycle_state.value,
                "rule_trace": routing_result.reasoning
            })

    # Store plan
    import uuid
    plan_id = str(uuid.uuid4())
    coordinator.database.store_plan(plan_id, {
        "items": plan_items,
        "created_by": "parallel_workflow",
        "mode": "LEGAL"
    })

    allowed = sum(1 for item in plan_items if item['status'] == 'ALLOWED')
    blocked = sum(1 for item in plan_items if item['status'] == 'BLOCKED')

    print(f"✓ Plan created: {plan_id}")
    print(f"  Total items: {len(plan_items):,}")
    print(f"  Allowed: {allowed:,}")
    print(f"  Blocked: {blocked:,}")
    print()

    # Show sample of planned moves
    print("Sample of planned moves:")
    print("-" * 70)
    for item in plan_items[:20]:
        file_name = Path(item['frm']).name
        target_dir = Path(item['to']).parent.name
        status_icon = "✓" if item['status'] == 'ALLOWED' else "✗"
        print(f"{status_icon} {file_name[:50]:<50} → {target_dir}")
    if len(plan_items) > 20:
        print(f"... and {len(plan_items) - 20:,} more")
    print()

    # Step 4: Confirmation
    if allowed == 0:
        print("No files can be moved (all blocked). Exiting.")
        coordinator.close()
        return

    print(f"Ready to move {allowed:,} files.")
    response = input("Proceed with file movement? (yes/no/dry-run): ").strip().lower()

    if response not in ['yes', 'y', 'dry-run', 'dry']:
        print("Cancelled.")
        coordinator.close()
        return

    dry_run = response in ['dry-run', 'dry']

    # Step 5: Execute plan
    print()
    print(f"[Step 4] {'DRY RUN - ' if dry_run else ''}Executing plan...")

    def progress_callback(message, progress):
        bar_length = 40
        filled = int(bar_length * progress / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        print(f"\r  [{bar}] {progress:.0f}% - {message}", end='', flush=True)

    undo_manager = UndoManager()
    executor = PlanExecutor(
        database=coordinator.database,
        undo_manager=undo_manager,
        progress_callback=progress_callback
    )

    try:
        start_exec = time.time()
        report = executor.execute_plan(
            plan_id=plan_id,
            dry_run=dry_run,
            skip_conflicts=True
        )
        exec_time = time.time() - start_exec

        print()
        print()
        print("=" * 70)
        print("EXECUTION REPORT")
        print("=" * 70)
        print(f"Success: {report.success}")
        print(f"Total Items: {report.total_items:,}")
        print(f"Successful: {report.successful:,}")
        print(f"Failed: {report.failed:,}")
        print(f"Skipped: {report.skipped:,}")
        print(f"Execution Time: {exec_time:.1f}s")

        if report.backup_id and not dry_run:
            print(f"Backup ID: {report.backup_id}")
            print("(Use this ID to undo the changes if needed)")

        print()
        print("=" * 70)
        print("TOTAL TIME SUMMARY")
        print("=" * 70)
        total_time = scan_time + process_time + exec_time
        print(f"Scan: {scan_time:.1f}s")
        print(f"Extract & Route: {process_time:.1f}s ({len(files_to_process)/process_time:.1f} files/sec)")
        print(f"Execute: {exec_time:.1f}s")
        print(f"Total: {total_time:.1f}s ({total_time/60:.1f} minutes)")
        print("=" * 70)

        if dry_run:
            print("✓ DRY RUN COMPLETE - No files were actually moved")
        elif report.success:
            print("✓ ALL FILES SUCCESSFULLY ORGANIZED")
        else:
            print("⚠ COMPLETED WITH SOME ERRORS")

    except Exception as e:
        print()
        print(f"\n✗ Execution failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        coordinator.close()


if __name__ == "__main__":
    main()
