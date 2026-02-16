#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete Legal Organization Workflow
Scan → Extract → Route → Plan → Apply

This script processes files from a source directory through the complete
legal organization pipeline and moves them to their target locations.

Uses DeepSeek LLM for legal extraction and decision-making.
"""

import sys
import os
from pathlib import Path

# Fix Unicode encoding for Windows console
if sys.platform == 'win32':
    try:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except:
        pass  # Fallback to default encoding

# Import DeepSeek configuration helper
from deepseek_config import get_deepseek_config, test_deepseek_connection

from file_organizer.legal.coordinator import LegalModeCoordinator
from file_organizer.routing.plan_executor import PlanExecutor
from file_organizer.undo.undo_manager import UndoManager

# Helper function for cross-platform console output
def safe_print(text):
    """Print text with fallback for Unicode issues on Windows."""
    try:
        print(text)
    except UnicodeEncodeError:
        # Replace Unicode chars with ASCII equivalents
        text = text.replace('✓', '[OK]').replace('✗', '[X]').replace('⚠', '[!]')
        print(text)


def main():
    # Configuration
    source_dir = Path("E:/Organization_Folder")
    legal_root = Path("E:/Organization_Folder")

    # Configure DeepSeek LLM
    print("Configuring DeepSeek LLM...")
    model_config = get_deepseek_config()

    # Test DeepSeek connection
    print()
    if not test_deepseek_connection(model_config):
        response = input("\nDeepSeek connection failed. Continue anyway? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            sys.exit(1)
    print()

    print("=" * 70)
    print("LEGAL FILE ORGANIZATION WORKFLOW")
    print("=" * 70)
    print(f"Source Directory: {source_dir}")
    print(f"Legal Root: {legal_root}")
    print(f"LLM Provider: DeepSeek ({model_config.name})")
    print()

    # Step 1: Initialize Legal Mode
    print("[Step 1] Initializing Legal Mode Coordinator...")
    coordinator = LegalModeCoordinator(legal_root)

    # TODO: Pass model_config to coordinator when LLM integration is added
    # Currently uses regex-based extraction, but model_config is ready for future use

    print(f"✓ Database: {coordinator.database.db_path}")
    print("  Note: Currently using pattern-based extraction.")
    print("        DeepSeek will be used for LLM features when enabled.")
    print()

    # Step 2: Scan directory for files
    print("[Step 2] Scanning directory for files...")
    all_files = list(source_dir.rglob("*"))
    files_to_process = [f for f in all_files if f.is_file()]

    print(f"✓ Found {len(files_to_process)} files")
    for f in files_to_process[:10]:  # Show first 10
        print(f"  - {f.name}")
    if len(files_to_process) > 10:
        print(f"  ... and {len(files_to_process) - 10} more")
    print()

    # Step 3: Extract & Route each file
    print("[Step 3] Extracting metadata and routing files...")
    processed_files = []
    file_ids = []

    for idx, file_path in enumerate(files_to_process, 1):
        print(f"\n[{idx}/{len(files_to_process)}] Processing: {file_path.name}")

        try:
            # Read file content
            ext = file_path.suffix.lower()
            if ext in {'.pdf', '.docx', '.xlsx', '.zip', '.jpg', '.png'}:
                # Binary files - use minimal content
                content = f"Binary file: {file_path.name} ({file_path.stat().st_size} bytes)"
            else:
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                except:
                    content = f"Unable to read: {file_path.name}"

            # Process through legal pipeline
            result = coordinator.process_file(file_path, content, file_path.name)

            processed_files.append(result)
            file_ids.append(result['file_id'])

            print(f"  ✓ Extracted")
            print(f"    File ID: {result['file_id'][:8]}...")
            print(f"    Target: {result['target_path']}")
            print(f"    Lifecycle: {result['lifecycle_state']}")
            print(f"    Confidence: {result['confidence']:.1%}")
            if result['case_binding']:
                print(f"    Case: {result['case_binding']}")
            print(f"    Entities: {result['entities_extracted']}")

        except Exception as e:
            print(f"  ✗ Error: {e}")
            continue

    print()
    print(f"✓ Successfully processed {len(processed_files)} files")
    print()

    if not processed_files:
        print("No files were successfully processed. Exiting.")
        return

    # Step 4: Create Plan
    print("[Step 4] Creating organization plan...")

    # Build plan items from processed files
    plan_items = []
    for result in processed_files:
        status = coordinator.get_file_status(result['file_id'])
        if not status:
            continue

        # Get extraction and routing info
        file_path = Path(status['current_path'])
        extraction_result = coordinator.get_extraction_result(result['file_id'])

        if extraction_result:
            routing_result = coordinator.router.route(
                extraction_result=extraction_result,
                file_path=file_path,
                current_state=None
            )

            # Determine status
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
                "file_id": result['file_id'],
                "action": "MOVE",
                "frm": str(file_path),
                "to": str(target_path),
                "status": plan_status,
                "blocked_reason": blocked_reason,
                "target_lifecycle_state": routing_result.lifecycle_state.value,
                "rule_trace": routing_result.reasoning
            })

    # Store plan in database
    import uuid
    plan_id = str(uuid.uuid4())
    coordinator.database.store_plan(plan_id, {
        "items": plan_items,
        "created_by": "workflow_script",
        "mode": "LEGAL"
    })

    print(f"✓ Plan created: {plan_id}")
    print(f"  Total items: {len(plan_items)}")

    allowed = sum(1 for item in plan_items if item['status'] == 'ALLOWED')
    blocked = sum(1 for item in plan_items if item['status'] == 'BLOCKED')

    print(f"  Allowed: {allowed}")
    print(f"  Blocked: {blocked}")
    print()

    # Show plan details
    print("Plan Details:")
    print("-" * 70)
    for item in plan_items:
        file_name = Path(item['frm']).name
        target_name = Path(item['to']).parent.name
        status_icon = "✓" if item['status'] == 'ALLOWED' else "✗"
        print(f"{status_icon} {file_name}")
        print(f"   → {target_name}/")
        if item['blocked_reason']:
            print(f"   Reason: {item['blocked_reason']}")
    print()

    # Step 5: Ask for confirmation
    if allowed == 0:
        print("No files can be moved (all blocked). Exiting.")
        coordinator.close()
        return

    print(f"Ready to move {allowed} files.")
    response = input("Proceed with file movement? (yes/no/dry-run): ").strip().lower()

    if response not in ['yes', 'y', 'dry-run', 'dry']:
        print("Cancelled.")
        coordinator.close()
        return

    dry_run = response in ['dry-run', 'dry']

    # Step 6: Execute Plan
    print()
    print(f"[Step 5] {'DRY RUN - ' if dry_run else ''}Executing plan...")

    def progress_callback(message, progress):
        bar_length = 40
        filled = int(bar_length * progress / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        print(f"\r  [{bar}] {progress:.0f}% - {message}", end='', flush=True)

    # Initialize executor
    undo_manager = UndoManager()
    executor = PlanExecutor(
        database=coordinator.database,
        undo_manager=undo_manager,
        progress_callback=progress_callback
    )

    try:
        report = executor.execute_plan(
            plan_id=plan_id,
            dry_run=dry_run,
            skip_conflicts=True
        )

        print()  # New line after progress bar
        print()
        print("=" * 70)
        print("EXECUTION REPORT")
        print("=" * 70)
        print(f"Success: {report.success}")
        print(f"Total Items: {report.total_items}")
        print(f"Successful: {report.successful}")
        print(f"Failed: {report.failed}")
        print(f"Skipped: {report.skipped}")
        print(f"Execution Time: {report.execution_time:.2f}s")

        if report.backup_id and not dry_run:
            print(f"Backup ID: {report.backup_id}")
            print("(Use this ID to undo the changes if needed)")

        if report.conflicts:
            print(f"\nConflicts ({len(report.conflicts)}):")
            for conflict in report.conflicts[:5]:
                print(f"  - {conflict.conflict_type}: {conflict.message}")
            if len(report.conflicts) > 5:
                print(f"  ... and {len(report.conflicts) - 5} more")

        if report.results:
            failed_results = [r for r in report.results if not r.success]
            if failed_results:
                print(f"\nFailed Operations ({len(failed_results)}):")
                for result in failed_results[:5]:
                    print(f"  - {Path(result.source_path).name}: {result.error}")

        print()

        if dry_run:
            print("✓ DRY RUN COMPLETE - No files were actually moved")
        elif report.success:
            print("✓ ALL FILES SUCCESSFULLY ORGANIZED")
        else:
            print("⚠ COMPLETED WITH ERRORS")

        print()

    except Exception as e:
        print()
        print(f"\n✗ Execution failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        coordinator.close()
        print("=" * 70)


if __name__ == "__main__":
    main()
