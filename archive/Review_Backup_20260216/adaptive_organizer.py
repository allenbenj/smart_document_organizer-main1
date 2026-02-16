#!/usr/bin/env python3
"""
Adaptive File Organizer - Continuously Learning AI System

This script implements an intelligent file organization system that:
1. Uses DeepSeek LLM to analyze files and learn patterns
2. Continuously refines regex patterns based on success/failure
3. Creates and optimizes folder structures
4. Intelligently renames files
5. Learns from user feedback

The system improves over time, building a "pristine" file structure.
"""

import sys
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

# Import DeepSeek configuration
from deepseek_config import get_deepseek_config, test_deepseek_connection

from file_organizer.learning import (
    LearningEngine,
    PatternRefiner,
    StructureOptimizer,
    IntelligentFileRenamer
)
from file_organizer.legal.coordinator import LegalModeCoordinator


class AdaptiveFileOrganizer:
    """
    Main adaptive file organization system.

    This system continuously learns and improves file organization by:
    - Analyzing documents with AI
    - Learning patterns from successes and failures
    - Creating optimal folder structures
    - Renaming files intelligently
    - Adapting to user preferences
    """

    def __init__(
        self,
        root_path: Path,
        model_config: Optional[Any] = None,
        learning_db_path: Optional[Path] = None,
        use_llm_for_files: bool = False  # Default OFF for large batches
    ):
        """
        Initialize the adaptive organizer.

        Args:
            root_path: Root directory to organize
            model_config: DeepSeek model configuration
            learning_db_path: Path for learning database
            use_llm_for_files: Use LLM for individual file analysis (slow, disable for large batches)
        """
        self.root_path = root_path
        self.root_path.mkdir(parents=True, exist_ok=True)
        self.use_llm_for_files = use_llm_for_files

        # Learning database
        db_path = learning_db_path or (root_path / ".organizer" / "learning.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize learning engine
        self.learning_engine = LearningEngine(
            db_path=db_path,
            model_config=model_config,
            llm_enabled=model_config is not None
        )

        # Initialize components
        self.pattern_refiner = PatternRefiner(self.learning_engine)
        self.structure_optimizer = StructureOptimizer(self.learning_engine)
        self.file_renamer = IntelligentFileRenamer(self.learning_engine)

        # Track processing stats
        self.stats = {
            "files_processed": 0,
            "files_renamed": 0,
            "folders_created": 0,
            "patterns_learned": 0,
            "user_corrections": 0
        }

        print(f"✓ Adaptive File Organizer initialized")
        print(f"  Root: {root_path}")
        print(f"  Learning DB: {db_path}")
        print(f"  LLM Enabled: {model_config is not None}")
        print(f"  LLM for files: {use_llm_for_files} (disable for large batches)")

    def scan_and_analyze(
        self,
        target_dir: Optional[Path] = None,
        recursive: bool = True,
        file_extensions: Optional[List[str]] = None,
        batch_size: int = 1000
    ) -> Dict[str, Any]:
        """
        Scan directory and analyze files.

        Args:
            target_dir: Directory to scan (default: root_path)
            recursive: Whether to scan recursively
            file_extensions: Filter by extensions (e.g., ['.pdf', '.docx'])
            batch_size: Process in batches for memory efficiency

        Returns:
            Analysis results
        """
        target = target_dir or self.root_path

        print(f"\n[Scanning] {target}")
        print("-" * 60)
        print("Counting files (this may take a moment for large directories)...")

        # Count files first
        file_count = 0
        files_generator = None

        if recursive:
            for ext in (file_extensions or ['*']):
                pattern = f"**/*{ext}" if ext != '*' else "**/*"
                for f in target.glob(pattern):
                    if f.is_file():
                        file_count += 1
                        if file_count % 10000 == 0:
                            print(f"\r  Counted {file_count:,} files...", end="", flush=True)
        else:
            for ext in (file_extensions or ['*']):
                pattern = f"*{ext}" if ext != '*' else "*"
                for f in target.glob(pattern):
                    if f.is_file():
                        file_count += 1

        print(f"\r✓ Found {file_count:,} files" + " " * 30)

        if file_count == 0:
            return {"total_files": 0, "files": [], "suggested_renames": [], "suggested_moves": [], "new_patterns": []}

        analysis = {
            "total_files": file_count,
            "files": [],
            "suggested_renames": [],
            "suggested_moves": [],
            "new_patterns": [],
            "errors": []
        }

        # Process files with progress tracking
        print(f"\nAnalyzing files...")
        print("-" * 60)

        start_time = time.time()
        processed = 0
        last_update = 0

        # Re-iterate for processing
        if recursive:
            files_iter = (f for ext in (file_extensions or ['*'])
                         for f in target.glob(f"**/*{ext}" if ext != '*' else "**/*")
                         if f.is_file())
        else:
            files_iter = (f for ext in (file_extensions or ['*'])
                         for f in target.glob(f"*{ext}" if ext != '*' else "*")
                         if f.is_file())

        for file_path in files_iter:
            processed += 1

            # Update progress every 100 files or every 2 seconds
            current_time = time.time()
            if processed % 100 == 0 or (current_time - last_update) > 2:
                elapsed = current_time - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                remaining = (file_count - processed) / rate if rate > 0 else 0
                percent = (processed / file_count) * 100

                # Format ETA
                if remaining > 3600:
                    eta = f"{remaining/3600:.1f}h"
                elif remaining > 60:
                    eta = f"{remaining/60:.1f}m"
                else:
                    eta = f"{remaining:.0f}s"

                progress_bar = self._progress_bar(percent)
                print(f"\r  {progress_bar} {percent:5.1f}% | {processed:,}/{file_count:,} | {rate:.0f}/s | ETA: {eta}   ", end="", flush=True)
                last_update = current_time

            try:
                file_analysis = self._analyze_file(file_path)

                # Only store summaries to save memory with large file counts
                if file_analysis.get("rename_suggestion"):
                    analysis["suggested_renames"].append(file_analysis["rename_suggestion"])

                if file_analysis.get("move_suggestion"):
                    analysis["suggested_moves"].append(file_analysis["move_suggestion"])

            except Exception as e:
                analysis["errors"].append({"file": str(file_path), "error": str(e)})

        # Final stats
        elapsed = time.time() - start_time
        print(f"\r  {self._progress_bar(100)} 100.0% | {file_count:,}/{file_count:,} | Done!          ")
        print(f"\n✓ Analyzed {file_count:,} files in {elapsed/60:.1f} minutes")
        print(f"  Rate: {file_count/elapsed:.0f} files/second")
        print(f"  Rename suggestions: {len(analysis['suggested_renames']):,}")
        print(f"  Move suggestions: {len(analysis['suggested_moves']):,}")
        if analysis["errors"]:
            print(f"  Errors: {len(analysis['errors']):,}")

        return analysis

    def _progress_bar(self, percent: float, width: int = 30) -> str:
        """Create a progress bar string"""
        filled = int(width * percent / 100)
        bar = '█' * filled + '░' * (width - filled)
        return f"[{bar}]"

    def _analyze_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze a single file"""
        analysis = {
            "path": str(file_path),
            "name": file_path.name,
            "extension": file_path.suffix,
            "size": file_path.stat().st_size,
            "entities": {},
            "rename_suggestion": None,
            "move_suggestion": None
        }

        # Try to read content
        content = None
        try:
            if file_path.suffix.lower() in ['.txt', '.md', '.py', '.json', '.csv']:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
            elif file_path.suffix.lower() in ['.pdf', '.docx']:
                content = f"[Binary: {file_path.name}]"
        except Exception:
            content = None

        # Extract entities using learned patterns
        if content:
            patterns = self.learning_engine.get_active_patterns()
            import re
            for pattern in patterns:
                try:
                    match = re.search(pattern.regex, content)
                    if match:
                        value = match.group(1) if match.groups() else match.group(0)
                        analysis["entities"][pattern.pattern_type] = value
                except re.error:
                    pass

        # Get rename suggestion (skip LLM for speed on large batches)
        rename_proposal = self.file_renamer.propose_rename(
            file_path, content if self.use_llm_for_files else None, analysis["entities"]
        )
        if rename_proposal.proposed_name != file_path.name and rename_proposal.confidence > 0.5:
            analysis["rename_suggestion"] = {
                "original": file_path.name,
                "suggested": rename_proposal.proposed_name,
                "confidence": rename_proposal.confidence,
                "reasoning": rename_proposal.reasoning
            }

        # Get folder suggestion (skip LLM for speed)
        if analysis["entities"] and self.use_llm_for_files:
            doc_type = analysis["entities"].get("document_type", "unknown")
            folder_suggestion = self.learning_engine.suggest_folder_structure(
                doc_type, analysis["entities"], self.root_path
            )
            if folder_suggestion.get("path"):
                analysis["move_suggestion"] = {
                    "current": str(file_path.parent),
                    "suggested": folder_suggestion["path"],
                    "confidence": folder_suggestion.get("confidence", 0.5),
                    "reasoning": folder_suggestion.get("reasoning", [])
                }

        self.stats["files_processed"] += 1
        return analysis

    def optimize_structure(
        self,
        target_dir: Optional[Path] = None,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Optimize folder structure using AI.

        Args:
            target_dir: Directory to optimize
            dry_run: If True, only show what would be done

        Returns:
            Optimization results
        """
        target = target_dir or self.root_path

        print(f"\n[Optimizing Structure] {target}")
        print("-" * 60)

        # First, analyze current structure
        analysis = self.structure_optimizer.analyze_structure(target)

        print(f"Current structure:")
        print(f"  Folders: {analysis.total_folders}")
        print(f"  Files: {analysis.total_files}")
        print(f"  Max depth: {analysis.max_depth}")
        print(f"  Empty folders: {len(analysis.empty_folders)}")
        print(f"  Overcrowded folders: {len(analysis.overcrowded_folders)}")
        print(f"  Inconsistent naming: {len(analysis.inconsistent_naming)}")

        # Get LLM suggestions
        print("\n  Consulting AI for optimization suggestions...")
        llm_suggestions = self.structure_optimizer.optimize_with_llm(target)

        if llm_suggestions.get("error"):
            print(f"  ⚠ LLM error: {llm_suggestions['error']}")
        else:
            print(f"  Analysis: {llm_suggestions.get('analysis', 'N/A')}")

            if llm_suggestions.get("issues"):
                print(f"\n  Issues found:")
                for issue in llm_suggestions["issues"][:5]:
                    print(f"    - {issue}")

            if llm_suggestions.get("recommended_structure"):
                print(f"\n  Recommended structure:")
                for folder in llm_suggestions["recommended_structure"][:10]:
                    print(f"    📁 {folder}")

        # Apply optimizations
        if not dry_run and llm_suggestions.get("recommended_structure"):
            print(f"\n  Applying optimizations...")
            results = self.structure_optimizer.apply_optimization(
                target, llm_suggestions, dry_run=False
            )

            self.stats["folders_created"] += len(results.get("folders_created", []))

            print(f"  ✓ Created {len(results.get('folders_created', []))} folders")
            print(f"  ✓ Renamed {len(results.get('folders_renamed', []))} folders")
            print(f"  ✓ Moved {len(results.get('files_moved', []))} files")

            if results.get("errors"):
                print(f"  ⚠ Errors: {len(results['errors'])}")

        return {
            "analysis": {
                "folders": analysis.total_folders,
                "files": analysis.total_files,
                "max_depth": analysis.max_depth,
                "empty_folders": len(analysis.empty_folders),
                "overcrowded": len(analysis.overcrowded_folders)
            },
            "llm_suggestions": llm_suggestions,
            "dry_run": dry_run
        }

    def rename_files(
        self,
        target_dir: Optional[Path] = None,
        min_confidence: float = 0.7,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Rename files using AI-suggested names.

        Args:
            target_dir: Directory to process
            min_confidence: Minimum confidence for automatic rename
            dry_run: If True, only show what would be done

        Returns:
            Rename results
        """
        target = target_dir or self.root_path

        print(f"\n[Renaming Files] {target}")
        print("-" * 60)

        # Get all files
        files = list(target.rglob("*"))
        files = [f for f in files if f.is_file()]

        print(f"Found {len(files)} files")

        # Get rename proposals
        proposals = []
        for file_path in files:
            content = None
            try:
                if file_path.suffix.lower() in ['.txt', '.md', '.py', '.json']:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')[:5000]
            except Exception:
                pass

            proposal = self.file_renamer.propose_rename(file_path, content)

            if proposal.proposed_name != file_path.name:
                proposals.append(proposal)

        print(f"Generated {len(proposals)} rename proposals")

        # Filter by confidence
        high_confidence = [p for p in proposals if p.confidence >= min_confidence]
        print(f"  High confidence (≥{min_confidence:.0%}): {len(high_confidence)}")

        # Show proposals
        if high_confidence:
            print(f"\nProposed renames:")
            for proposal in high_confidence[:10]:
                print(f"  {proposal.original_path.name}")
                print(f"    → {proposal.proposed_name} ({proposal.confidence:.0%})")

        # Apply if not dry run
        results = {"applied": [], "skipped": [], "errors": []}

        if not dry_run and high_confidence:
            print(f"\nApplying renames...")
            results = self.file_renamer.batch_apply(
                high_confidence,
                min_confidence=min_confidence,
                dry_run=False
            )

            self.stats["files_renamed"] += len(results.get("applied", []))

            print(f"  ✓ Renamed {len(results.get('applied', []))} files")

            if results.get("errors"):
                print(f"  ⚠ Errors: {len(results['errors'])}")

        return {
            "proposals": len(proposals),
            "high_confidence": len(high_confidence),
            "results": results,
            "dry_run": dry_run
        }

    def refine_patterns(self) -> Dict[str, Any]:
        """
        Refine patterns based on learning.

        Returns:
            Refinement results
        """
        print(f"\n[Refining Patterns]")
        print("-" * 60)

        # Get current stats
        stats_before = self.learning_engine.get_learning_stats()
        print(f"Before refinement:")
        print(f"  Total patterns: {stats_before['total_patterns']}")
        print(f"  Learned: {stats_before['learned_patterns']}")
        print(f"  High confidence: {stats_before['high_confidence_patterns']}")
        print(f"  Average confidence: {stats_before['average_confidence']:.1%}")

        # Analyze patterns
        analyses = self.pattern_refiner.analyze_patterns()

        to_refine = [a for a in analyses if a.recommendation == "refine"]
        to_deprecate = [a for a in analyses if a.recommendation == "deprecate"]
        to_merge = [a for a in analyses if a.recommendation == "merge"]

        print(f"\nPattern analysis:")
        print(f"  Need refinement: {len(to_refine)}")
        print(f"  To deprecate: {len(to_deprecate)}")
        print(f"  To merge: {len(to_merge)}")

        # Apply refinements
        results = self.pattern_refiner.refine_underperforming_patterns()

        self.stats["patterns_learned"] += len(results.get("refined", []))

        # Get stats after
        stats_after = self.learning_engine.get_learning_stats()
        print(f"\nAfter refinement:")
        print(f"  Total patterns: {stats_after['total_patterns']}")
        print(f"  Learned: {stats_after['learned_patterns']}")
        print(f"  High confidence: {stats_after['high_confidence_patterns']}")
        print(f"  Average confidence: {stats_after['average_confidence']:.1%}")

        return {
            "before": stats_before,
            "after": stats_after,
            "refinements": results
        }

    def process_user_correction(
        self,
        file_path: Path,
        corrections: Dict[str, Any]
    ):
        """
        Learn from user correction.

        Args:
            file_path: File that was corrected
            corrections: Dictionary of corrections
        """
        print(f"\n[Learning from Correction]")
        print(f"  File: {file_path.name}")
        print(f"  Corrections: {json.dumps(corrections, indent=4)}")

        # Read file content
        content = ""
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            pass

        # Learn from the correction
        insights = self.learning_engine.learn_from_file(
            file_path=file_path,
            content=content,
            extraction_result={},  # What we extracted
            user_corrections=corrections
        )

        self.stats["user_corrections"] += 1

        if insights.get("new_patterns"):
            print(f"  ✓ Created {len(insights['new_patterns'])} new patterns")

        if insights.get("confidence_updates"):
            print(f"  ✓ Updated {len(insights['confidence_updates'])} pattern confidences")

        return insights

    def run_continuous(
        self,
        target_dir: Optional[Path] = None,
        interval_minutes: int = 30,
        dry_run: bool = True
    ):
        """
        Run continuous organization loop.

        Args:
            target_dir: Directory to organize
            interval_minutes: Minutes between cycles
            dry_run: If True, don't make changes
        """
        target = target_dir or self.root_path

        print("=" * 70)
        print("CONTINUOUS ADAPTIVE FILE ORGANIZATION")
        print("=" * 70)
        print(f"Target: {target}")
        print(f"Interval: {interval_minutes} minutes")
        print(f"Dry Run: {dry_run}")
        print()
        print("Press Ctrl+C to stop")
        print("=" * 70)

        cycle = 0
        try:
            while True:
                cycle += 1
                print(f"\n{'=' * 70}")
                print(f"CYCLE {cycle} - {time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'=' * 70}")

                # Scan and analyze
                analysis = self.scan_and_analyze(target)

                # Optimize structure
                self.optimize_structure(target, dry_run=dry_run)

                # Rename files
                self.rename_files(target, dry_run=dry_run)

                # Refine patterns
                self.refine_patterns()

                # Print stats
                print(f"\n[Session Stats]")
                print(f"  Files processed: {self.stats['files_processed']}")
                print(f"  Files renamed: {self.stats['files_renamed']}")
                print(f"  Folders created: {self.stats['folders_created']}")
                print(f"  Patterns learned: {self.stats['patterns_learned']}")
                print(f"  User corrections: {self.stats['user_corrections']}")

                print(f"\nSleeping for {interval_minutes} minutes...")
                time.sleep(interval_minutes * 60)

        except KeyboardInterrupt:
            print("\n\nStopped by user.")
        finally:
            self.cleanup()

    def get_stats(self) -> Dict[str, Any]:
        """Get current stats"""
        learning_stats = self.learning_engine.get_learning_stats()
        return {
            "session": self.stats,
            "learning": learning_stats
        }

    def cleanup(self):
        """Cleanup resources"""
        self.learning_engine.cleanup()


def main():
    # ============================================================
    # CONFIGURE YOUR PATH HERE
    # ============================================================
    source_dir = Path("E:/Organization_Folder/01_Court_Information/")  # <-- CHANGE THIS TO YOUR FOLDER
    # ============================================================

    print("=" * 70)
    print("ADAPTIVE FILE ORGANIZER")
    print("Continuously Learning AI File Organization System")
    print("=" * 70)
    print()

    # Configure DeepSeek
    print("Configuring DeepSeek LLM...")
    model_config = get_deepseek_config()

    # Test connection
    print()
    if not test_deepseek_connection(model_config):
        response = input("\nContinue without LLM? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            sys.exit(1)
        model_config = None
    print()

    # Ask about LLM mode for file analysis
    print("=" * 70)
    print("FILE ANALYSIS MODE")
    print("=" * 70)
    print("For large file counts (1000+), LLM analysis per file is SLOW.")
    print("  - Pattern mode: ~1000+ files/sec (regex only)")
    print("  - LLM mode: ~1-5 files/sec (calls DeepSeek for each file)")
    print()
    use_llm = input("Use LLM for individual file analysis? (yes/no, default=no): ").strip().lower()
    use_llm_for_files = use_llm in ['yes', 'y']
    print(f"✓ Mode: {'LLM (slow but thorough)' if use_llm_for_files else 'Pattern-only (fast)'}")
    print()

    # Initialize organizer
    organizer = AdaptiveFileOrganizer(
        root_path=source_dir,
        model_config=model_config,
        use_llm_for_files=use_llm_for_files
    )

    # Show menu
    while True:
        print("\n" + "=" * 50)
        print("MENU")
        print("=" * 50)
        print("1. Scan and analyze files")
        print("2. Optimize folder structure")
        print("3. Rename files intelligently")
        print("4. Refine patterns")
        print("5. Run continuous mode")
        print("6. View stats")
        print("7. Exit")
        print()

        choice = input("Select option (1-7): ").strip()

        if choice == "1":
            organizer.scan_and_analyze()
        elif choice == "2":
            dry = input("Dry run? (yes/no): ").strip().lower() in ['yes', 'y', '']
            organizer.optimize_structure(dry_run=dry)
        elif choice == "3":
            dry = input("Dry run? (yes/no): ").strip().lower() in ['yes', 'y', '']
            organizer.rename_files(dry_run=dry)
        elif choice == "4":
            organizer.refine_patterns()
        elif choice == "5":
            interval = input("Interval in minutes (default 30): ").strip()
            interval = int(interval) if interval else 30
            dry = input("Dry run? (yes/no): ").strip().lower() in ['yes', 'y', '']
            organizer.run_continuous(interval_minutes=interval, dry_run=dry)
        elif choice == "6":
            stats = organizer.get_stats()
            print(json.dumps(stats, indent=2))
        elif choice == "7":
            organizer.cleanup()
            print("Goodbye!")
            break
        else:
            print("Invalid option")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
