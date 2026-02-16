#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smart Adaptive Organizer - Index First, LLM Analyzes Aggregated Data

This is a smarter approach than calling LLM per file:
1. FAST SCAN: Index all files using regex → SQLite (~1000s files/sec)
2. AGGREGATE: Build statistics about entities, patterns, folders
3. LLM ANALYZE: Send aggregated data to LLM for intelligent decisions
4. APPLY: Execute LLM recommendations in batches

The LLM sees the big picture and makes holistic decisions instead of
file-by-file analysis which is slow and lacks context.
"""

import os
import sys
import re
import time
import json
import sqlite3
from pathlib import Path
from typing import Optional, Dict, List, Any

# Fix Unicode encoding for Windows console
if sys.platform == 'win32':
    try:
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except:
        pass  # Fallback to default encoding

from file_organizer.learning.file_index import FileIndex, SmartAnalyzer
from deepseek_config import get_deepseek_config


# Entity extraction patterns
DEFAULT_PATTERNS = [
    # Case numbers
    ("case_number", r"(\d{2}[A-Z]{2}\d{5,7})"),
    ("case_number", r"(?:case|no|#)[:\s]*(\d{2,4}[A-Z]{0,2}[-]?\d{3,7})"),

    # Dates
    ("date", r"(\d{4}[-/]\d{2}[-/]\d{2})"),  # YYYY-MM-DD
    ("date", r"(\d{2}[-/]\d{2}[-/]\d{4})"),  # MM-DD-YYYY
    ("date", r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})"),

    # Legal document types
    ("doc_type", r"(motion|order|judgment|complaint|response|petition|notice|subpoena|affidavit|decree|stipulation|brief)"),
    ("doc_type", r"(deposition|discovery|interrogator|exhibit|pleading|summons|warrant|indictment)"),

    # Party names (capitalized words before v. or vs)
    ("party", r"([A-Z][a-z]+)\s+(?:v\.?|vs\.?)\s+"),
    ("party", r"\s+(?:v\.?|vs\.?)\s+([A-Z][a-z]+)"),

    # Court types
    ("court", r"(district|circuit|supreme|appellate|superior|municipal|family|probate|bankruptcy|federal)"),

    # Document IDs
    ("doc_id", r"(?:doc|document|id)[:\s#]*(\d{4,10})"),

    # Invoice/Account numbers
    ("invoice", r"(?:inv|invoice)[:\s#]*(\w+-?\d+)"),
    ("account", r"(?:acct|account)[:\s#]*(\d{6,12})"),

    # Amounts
    ("amount", r"\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)"),

    # Email addresses
    ("email", r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"),

    # Phone numbers
    ("phone", r"(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})"),

    # SSN (last 4 or full)
    ("ssn_last4", r"(?:SSN|xxx-xx-)(\d{4})"),

    # Years
    ("year", r"(?:^|[^\d])(\d{4})(?:[^\d]|$)"),
]


def print_header(text: str):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(f" {text}")
    print("=" * 60)


def print_progress(processed: int, total: int, current_file: str):
    """Display progress bar"""
    pct = (processed / total) * 100
    bar_len = 40
    filled = int(bar_len * processed / total)
    bar = "█" * filled + "░" * (bar_len - filled)

    # Truncate filename
    if len(current_file) > 30:
        current_file = "..." + current_file[-27:]

    print(f"\r[{bar}] {pct:5.1f}% ({processed:,}/{total:,}) {current_file:<30}", end="", flush=True)


def format_size(size_bytes: int) -> str:
    """Format file size"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


class SmartOrganizer:
    """
    Smart file organizer that indexes first, then uses LLM on aggregated data.
    """

    def __init__(self, root_path: str):
        """Initialize the organizer"""
        self.root_path = Path(root_path)
        self.db_dir = self.root_path / ".organizer"
        self.db_dir.mkdir(parents=True, exist_ok=True)

        self.index = FileIndex(self.db_dir / "file_index.db")
        self.analyzer: Optional[SmartAnalyzer] = None

        print(f"Smart Organizer initialized")
        print(f"  Root: {self.root_path}")
        print(f"  Database: {self.db_dir / 'file_index.db'}")

    def clear_database(self):
        """Clear all data from the database and start fresh"""
        print_header("CLEAR DATABASE")

        db_path = self.db_dir / "file_index.db"

        print(f"\n⚠️  WARNING: This will delete ALL indexed data!")
        print(f"   Database: {db_path}")

        # Show current stats
        try:
            stats = self.index.get_statistics(root_path=self.root_path)
            print(f"\n   Current data:")
            print(f"   - {stats.get('total_files', 0):,} indexed files")
            print(f"   - {len(stats.get('top_folders', [])):,} folders tracked")
            print(f"   - {sum(len(v) for v in stats.get('entities', {}).values()):,} entities extracted")
        except Exception:
            print("   (No data currently in database)")

        confirm = input("\nType 'DELETE' to confirm: ").strip().upper()

        if confirm != 'DELETE':
            print("Cancelled.")
            return

        # Close any connections
        if self.analyzer:
            self.analyzer.cleanup()
            self.analyzer = None

        # Force close the index connection
        self.index = None

        # Force garbage collection to release file handles
        import gc
        gc.collect()

        # Small delay to let Windows release the file
        import time
        time.sleep(0.5)

        # Delete and recreate database
        try:
            if db_path.exists():
                db_path.unlink()
                print(f"\n✓ Deleted: {db_path}")

            # Also delete any SQLite journal/wal files
            for suffix in ['-journal', '-wal', '-shm']:
                journal = Path(str(db_path) + suffix)
                if journal.exists():
                    journal.unlink()
                    print(f"✓ Deleted: {journal.name}")

            # Recreate fresh database
            self.index = FileIndex(db_path)
            print("✓ Created fresh database")
            print("\n✅ Database cleared! Run 'Scan & Index' to rebuild.")

        except PermissionError as e:
            print(f"\n❌ File still locked. Try:")
            print(f"   1. Exit this program (option 0)")
            print(f"   2. Manually delete: {db_path}")
            print(f"   3. Restart the program")
        except Exception as e:
            print(f"\n❌ Error clearing database: {e}")

    def generate_file_level_actions(self):
        """Generate per-file move/rename actions based on extracted entities."""
        print_header("FILE-LEVEL ACTION GENERATOR")

        root_only_input = input("\nOnly organize files in the root folder? (y/n, default y): ").strip().lower()
        root_only = root_only_input in ("y", "yes", "")

        llm_input = input("Use LLM to extract metadata? (y/n, default y): ").strip().lower()
        llm_enabled = llm_input in ("y", "yes", "")

        clear_input = input("Clear existing pending file-level actions first? (y/n, default y): ").strip().lower()
        if clear_input in ("y", "yes", ""):
            cleared = self.index.clear_pending_actions(action_types=["move_file"])
            if cleared:
                print(f"Cleared {cleared} pending file-level actions.")

        review_input = input("Use review queue for low-confidence files? (y/n, default y): ").strip().lower()
        use_review_queue = review_input in ("y", "yes", "")

        llm_model = None
        if llm_enabled:
            try:
                from file_organizer.models.openai_model import OpenAIModel
                from deepseek_config import get_deepseek_config

                config = get_deepseek_config()
                llm_model = OpenAIModel(config)
                llm_model.initialize()
            except Exception as e:
                print(f"\n⚠️  LLM unavailable, falling back to patterns only: {e}")
                llm_enabled = False

        # Derive structure mapping from existing folders
        structure_map = self._derive_structure_map()

        # Gather files from index
        with sqlite3.connect(self.index.db_path) as conn:
            conn.row_factory = sqlite3.Row
            root_prefix = str(self.root_path.resolve()).rstrip("\\/") + os.sep + "%"
            query = """
                SELECT file_id, path, name, extension, parent_folder, doc_type, suggested_name
                FROM files
                WHERE LOWER(path) LIKE LOWER(?)
            """
            params = [root_prefix]
            if root_only:
                query += " AND parent_folder = ''"
            files = conn.execute(query, params).fetchall()

        if not files:
            print("\n⚠️  No files found to generate actions.")
            return

        analysis_id = self.index.create_analysis_record(
            analysis_type="file_level",
            input_summary=f"File-level action generator (root_only={root_only}, llm={llm_enabled})",
            recommendations={"root_only": root_only, "file_count": len(files), "llm": llm_enabled},
        )

        actions_created = 0
        skipped = 0

        from file_organizer.learning.content_extractor import get_extractor
        extractor = get_extractor()

        for row in files:
            file_id = row["file_id"]
            path = Path(row["path"])
            name = row["name"]
            extension = (row["extension"] or "").lower()
            doc_type = row["doc_type"] or ""
            suggested_name = row["suggested_name"] or ""

            # Extract metadata from content (patterns) + optional LLM
            content_result = extractor.extract_content(path, max_chars=6000)
            pattern_doc_type = content_result.get("doc_type") or doc_type
            entities = content_result.get("entities", {})
            case_number = self._pick_case_number(entities.get("case_number", []), name)
            date_value = self._pick_date(entities.get("date", []))

            llm_meta = {}
            if llm_enabled and llm_model:
                llm_meta = self._extract_llm_metadata(
                    llm_model, content_result.get("text", ""), name
                )

            doc_type = self._prefer_value(pattern_doc_type, llm_meta.get("doc_type"))
            case_number = self._prefer_value(case_number, llm_meta.get("case_number"))
            date_value = self._prefer_value(date_value, llm_meta.get("date"))

            target_dir, confidence = self._suggest_target_dir(
                name,
                extension,
                doc_type,
                case_number,
                structure_map,
            )
            if not target_dir:
                skipped += 1
                continue

            if use_review_queue and confidence < 0.55:
                target_dir = "00_Review/Unclassified"

            target_name = self._resolve_target_name(name, extension, suggested_name, date_value)
            target_path = Path(target_dir) / target_name

            # Skip if already in place
            if path.resolve() == (self.root_path / target_path).resolve():
                skipped += 1
                continue

            self.index.add_proposed_action(
                analysis_id=analysis_id,
                action_type="move_file",
                file_id=file_id,
                current_value=str(path),
                proposed_value=str(target_path),
                confidence=confidence,
            )
            actions_created += 1

        print(f"\nGenerated {actions_created} move actions.")
        print(f"Skipped: {skipped}")
        print("\nRun 'Show Pending Actions' (option 6) to review, then execute (option 7).")

        if llm_model:
            llm_model.cleanup()

    def _get_entity_values(self, file_id: str, entity_type: str) -> List[str]:
        with sqlite3.connect(self.index.db_path) as conn:
            rows = conn.execute(
                """
                SELECT entity_value
                FROM file_entities
                WHERE file_id = ? AND entity_type = ?
                """,
                (file_id, entity_type),
            ).fetchall()
            return [r[0] for r in rows if r and r[0]]

    def _pick_case_number(self, candidates: List[str], filename: str) -> str:
        if candidates:
            return candidates[0]
        match = re.search(r"(\d{1,2}[-:]?[A-Z]{2,3}[-:]?\d{3,6})", filename)
        return match.group(1) if match else "Unknown_Case"

    def _resolve_target_name(self, name: str, extension: str, suggested_name: str, date_value: str) -> str:
        if suggested_name:
            suggested = suggested_name
            if not Path(suggested).suffix and extension:
                suggested = f"{suggested}{extension}"
            name = suggested

        if date_value and not name.startswith(date_value):
            name = f"{date_value}_{name}"

        return name

    def _pick_date(self, candidates: List[str]) -> str:
        for value in candidates:
            if value:
                return value.replace("/", "-")
        return ""

    def _prefer_value(self, primary: str, secondary: str) -> str:
        return primary or secondary or ""

    def _extract_llm_metadata(self, model, content: str, filename: str) -> Dict[str, str]:
        if not content:
            return {}

        prompt = f"""Extract legal document metadata from the text. Return JSON only.

Fields:
- doc_type (e.g., motion, order, complaint, affidavit)
- case_number
- date (YYYY-MM-DD if possible)
- parties (string)
- court (string)

Filename: {filename}

Text:
{content[:3000]}
"""
        try:
            response = model.generate(prompt)
            return self._parse_json_response(response)
        except Exception:
            return {}

    def _parse_json_response(self, response: str) -> Dict[str, str]:
        if not response:
            return {}
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            start = response.find("{")
            end = response.rfind("}")
            if start == -1 or end == -1 or end <= start:
                return {}
            try:
                return json.loads(response[start:end + 1])
            except json.JSONDecodeError:
                return {}

    def _suggest_target_dir(
        self,
        filename: str,
        extension: str,
        doc_type: str,
        case_number: str,
        structure_map: Dict[str, str],
    ) -> tuple[str, float]:
        doc_type = doc_type.strip().lower()

        if doc_type and doc_type in structure_map:
            target = structure_map[doc_type].format(case_number=case_number)
            return (target, 0.75)

        if doc_type in ("contract", "agreement"):
            return ("05_Administrative/Contracts", 0.7)
        if doc_type in ("invoice", "receipt", "billing"):
            return ("05_Administrative/Billing", 0.7)
        if doc_type in ("report", "analysis"):
            return ("04_Research_Analysis", 0.6)
        if doc_type in ("letter",):
            return ("05_Administrative/Correspondence", 0.6)

        # Extension-based fallback
        if extension in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"}:
            return ("02_Evidence/Images", 0.6)
        if extension in {".mp4", ".avi", ".mkv", ".mov", ".wmv"}:
            return ("06_Media_Files/Video", 0.6)
        if extension in {".mp3", ".wav", ".flac", ".m4a", ".ogg"}:
            return ("06_Media_Files/Audio", 0.6)
        if extension in {".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".md"}:
            fallback = structure_map.get(
                "documents",
                "01_Cases/{case_number}/01_Court_Filings/Documents",
            )
            return (fallback.format(case_number=case_number), 0.55)

        return ("00_Review/Unclassified", 0.4)

    def _derive_structure_map(self) -> Dict[str, str]:
        """Derive folder mapping from existing structure."""
        doc_types = [
            "motion", "order", "complaint", "affidavit", "subpoena", "brief",
            "petition", "notice", "discovery", "exhibit", "deposition",
            "warrant", "indictment", "judgment", "settlement", "documents",
        ]
        existing_dirs = [p for p in self.root_path.iterdir() if p.is_dir()]
        existing_names = {p.name.lower(): p.name for p in existing_dirs}

        base_cases = self._pick_existing_folder(["01_cases", "cases"], existing_names)
        if not base_cases:
            base_cases = "01_Cases"

        court_filings = "01_Court_Filings"

        mapping: Dict[str, str] = {}
        for doc_type in doc_types:
            best = self._match_folder(doc_type, existing_names)
            if best:
                mapping[doc_type] = best
            else:
                mapping[doc_type] = str(
                    Path(base_cases) / "{case_number}" / court_filings / doc_type.title().replace("_", " ")
                )

        # Documents fallback
        mapping["documents"] = str(Path(base_cases) / "{case_number}" / court_filings / "Documents")
        return mapping

    def _pick_existing_folder(self, candidates: List[str], existing_names: Dict[str, str]) -> str:
        for candidate in candidates:
            if candidate in existing_names:
                return existing_names[candidate]
        return ""

    def _match_folder(self, doc_type: str, existing_names: Dict[str, str]) -> str:
        doc_type_norm = doc_type.replace("_", " ").lower()
        for name_lower, original in existing_names.items():
            if doc_type_norm in name_lower:
                return original
        return ""

    def scan(
        self,
        extensions: Optional[List[str]] = None,
        patterns: Optional[List[tuple]] = None
    ):
        """
        PHASE 1: Fast scan and index all files.

        Extracts:
        - File metadata (size, date, location)
        - Entities from filenames (dates, case numbers, etc.)
        - Content from PDFs/DOCX (if libraries available)
        - Document types from content analysis
        - Filename quality scores
        """
        print_header("PHASE 1: INDEXING FILES")

        if patterns is None:
            patterns = DEFAULT_PATTERNS

        print(f"Using {len(patterns)} entity extraction patterns")

        # Check if content extraction is available
        try:
            from src.file_organizer.learning.content_extractor import get_extractor
            extractor = get_extractor()
            if extractor._pdf_extractor:
                print(f"✓ PDF extraction: {extractor._pdf_extractor}")
            else:
                print("⚠ PDF extraction not available (install pdfplumber or PyPDF2)")
            if extractor._docx_available:
                print("✓ DOCX extraction: python-docx")
            print()
        except:
            print("⚠ Content extraction not available")
            print()

        stats = self.index.scan_directory(
            self.root_path,
            patterns=patterns,
            extensions=extensions,
            progress_callback=print_progress,
            reset_root=True,
        )

        print()  # New line after progress bar
        print()
        print("INDEXING COMPLETE")
        print(f"  Files indexed: {stats['indexed']:,}")
        print(f"  Errors: {stats['errors']:,}")
        print(f"  Time: {stats['elapsed']:.1f}s")
        print(f"  Rate: {stats['rate']:.0f} files/sec")
        print(f"  Unique folders: {stats['folders']}")
        print(f"  Entity extractions:")
        for entity, count in stats['entities_found'].most_common(10):
            print(f"    {entity}: {count:,}")

    def analyze(self):
        """
        PHASE 2: Have LLM analyze the aggregated data.
        """
        print_header("PHASE 2: LLM ANALYSIS")

        if self.analyzer is None:
            config = get_deepseek_config()
            self.analyzer = SmartAnalyzer(self.index, config)

        print("Gathering statistics from index...")
        stats = self.index.get_statistics(root_path=self.root_path)

        print(f"\nINDEX STATISTICS:")
        print(f"  Total files: {stats['total_files']:,}")
        print(f"  Total size: {format_size(stats['total_size'])}")
        print(f"  Top extensions: {', '.join(e['extension'] for e in stats['extensions'][:5])}")
        print(f"  Unique folders: {len(stats['top_folders'])}")
        print(f"  Entities found: {sum(len(v) for v in stats['entities'].values())}")

        print("\nSending to LLM for analysis...")
        print("(LLM sees ALL indexed data at once, not file-by-file)")

        try:
            recommendations = self.analyzer.analyze_structure(root_path=self.root_path)

            print("\n" + "-" * 50)
            print("LLM ANALYSIS RESULTS")
            print("-" * 50)

            if "analysis" in recommendations:
                analysis = recommendations["analysis"]
                print(f"\nOrganization Score: {analysis.get('organization_score', 'N/A')}/100")

                print("\nPatterns Found:")
                for p in analysis.get("patterns_found", []):
                    print(f"  • {p}")

                print("\nProblems Identified:")
                for p in analysis.get("problems_identified", []):
                    print(f"  ⚠ {p}")

            if "recommended_structure" in recommendations:
                struct = recommendations["recommended_structure"]
                print("\nRecommended Folders to Create:")
                for folder in struct.get("folders_to_create", [])[:10]:
                    print(f"  📁 {folder.get('path')}")
                    print(f"     Purpose: {folder.get('purpose')}")

            if "naming_convention" in recommendations:
                naming = recommendations["naming_convention"]
                print(f"\nRecommended Naming Convention:")
                print(f"  Pattern: {naming.get('pattern')}")
                print(f"  Components: {', '.join(naming.get('components', []))}")

            if "priority_recommendations" in recommendations:
                print("\nPriority Actions:")
                for i, rec in enumerate(recommendations.get("priority_recommendations", [])[:5], 1):
                    print(f"  {i}. {rec}")

            if "actions" in recommendations:
                print(f"\nTotal Actions Proposed: {len(recommendations.get('actions', []))}")

            return recommendations

        except Exception as e:
            print(f"\n❌ LLM Analysis failed: {e}")
            return None

    def run_full_pipeline(self):
        """Run the recommended end-to-end workflow in sequence."""
        print_header("FULL PIPELINE")
        print("This runs:")
        print("  1) Scan & Index Files")
        print("  2) Process Files (comprehensive)")
        print("  3) Find All Duplicates")
        print("  4) Consolidate Duplicates (optional)")
        print("  5) LLM Analyze Structure")
        print("  6) Execute Recommendations (optional)")
        print("  7) Generate Report")

        confirm = input("\nRun full pipeline now? (y/n): ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Cancelled.")
            return

        self.scan()
        self.process_files_comprehensive_interactive()
        self.find_all_duplicates_enhanced()

        do_consolidate = input("\nConsolidate duplicates now? (y/n, default y): ").strip().lower()
        if do_consolidate in ("", "y", "yes"):
            self.consolidate_duplicates(filename_pattern=None, min_copies=2)

        self.analyze()

        do_execute = input("\nExecute recommendations now? (y/n, default n): ").strip().lower()
        if do_execute in ("y", "yes"):
            self.execute_all_actions()

        self.generate_comprehensive_report()

    def analyze_folder(self, folder: str):
        """Analyze a specific folder in detail"""
        print_header(f"ANALYZING FOLDER: {folder}")

        if self.analyzer is None:
            config = get_deepseek_config()
            self.analyzer = SmartAnalyzer(self.index, config)

        try:
            result = self.analyzer.analyze_folder(folder)

            print(f"\nFolder Purpose: {result.get('folder_purpose', 'Unknown')}")

            if "document_types_found" in result:
                print("\nDocument Types:")
                for dt in result.get("document_types_found", []):
                    print(f"  • {dt}")

            if "suggested_subfolders" in result:
                print("\nSuggested Subfolders:")
                for sub in result.get("suggested_subfolders", []):
                    print(f"  📁 {sub.get('name')}")
                    print(f"     For: {sub.get('purpose')}")

            if "misplaced_files" in result:
                print("\nMisplaced Files:")
                for mf in result.get("misplaced_files", [])[:10]:
                    print(f"  ⚠ {mf.get('file')} → {mf.get('suggested_location')}")

            return result

        except Exception as e:
            print(f"\n❌ Analysis failed: {e}")
            return None

    def get_rename_suggestions(self, extension: str = None):
        """Get intelligent rename suggestions"""
        print_header("RENAME SUGGESTIONS")

        if self.analyzer is None:
            config = get_deepseek_config()
            self.analyzer = SmartAnalyzer(self.index, config)

        try:
            result = self.analyzer.suggest_renames_for_pattern(extension=extension)

            if "naming_convention" in result:
                print(f"\nRecommended Convention: {result['naming_convention']}")

            if "renames" in result:
                print(f"\nRename Suggestions ({len(result['renames'])} files):")
                for r in result.get("renames", [])[:20]:
                    print(f"\n  Current:  {r.get('current')}")
                    print(f"  Suggest:  {r.get('suggested')}")
                    print(f"  Reason:   {r.get('reason')}")

            return result

        except Exception as e:
            print(f"\n❌ Failed: {e}")
            return None

    def show_statistics(self):
        """Show current index statistics"""
        print_header("INDEX STATISTICS")

        stats = self.index.get_statistics(root_path=self.root_path)

        print(f"\nOVERVIEW")
        print(f"  Total Files: {stats['total_files']:,}")
        print(f"  Total Size: {format_size(stats['total_size'])}")

        print(f"\nFILE TYPES")
        for ext in stats['extensions'][:15]:
            print(f"  {ext['extension'] or '(no ext)':<10} {ext['count']:>8,} files  ({format_size(ext['size'] or 0):>10})")

        print(f"\nFOLDER DEPTH DISTRIBUTION")
        for d in stats['depth_distribution']:
            bar = "█" * min(d['count'] // 100, 40)
            print(f"  Depth {d['depth']}: {d['count']:>6,} {bar}")

        print(f"\nTOP ENTITIES EXTRACTED")
        for entity_type, values in stats['entities'].items():
            print(f"\n  {entity_type.upper()}:")
            for v in values[:5]:
                print(f"    {v['value']:<30} ({v['count']:,} files)")

        if stats['potential_duplicates']:
            print(f"\nPOTENTIAL DUPLICATES (same filename)")
            for d in stats['potential_duplicates'][:10]:
                print(f"  {d['name']}: {d['count']} copies")

    def show_pending_actions(self):
        """Show actions proposed by LLM analysis"""
        print_header("PENDING ACTIONS")

        actions = self.index.get_pending_actions()

        if not actions:
            print("\nNo pending actions. Run analysis first.")
            return

        print(f"\nTotal pending actions: {len(actions)}")

        # Group by type
        by_type = {}
        for a in actions:
            t = a.get('action_type', 'unknown')
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(a)

        for action_type, items in by_type.items():
            print(f"\n{action_type.upper()}: {len(items)} actions")
            for item in items[:5]:
                current = item.get('current_value') or '(all matching)'
                proposed = item.get('proposed_value') or '(action)'
                reason = item.get('file_id') or ''  # reason stored in file_id

                if action_type == "create_folder":
                    print(f"  📁 Create: {proposed}")
                    if reason:
                        print(f"     Reason: {reason}")
                elif action_type in ["delete_files", "delete"]:
                    print(f"  🗑️  Delete: {current}")
                    if reason:
                        print(f"     Reason: {reason}")
                elif action_type in ["move_pattern", "move"]:
                    print(f"  📦 Move: {current}")
                    print(f"     To: {proposed}")
                elif action_type in ["rename_pattern", "rename"]:
                    print(f"  ✏️  Rename pattern: {current}")
                    print(f"     New pattern: {proposed}")
                elif action_type in ["consolidate_folders", "consolidate"]:
                    print(f"  🔗 Consolidate: {current}")
                    print(f"     Into: {proposed}")
                else:
                    print(f"  • {current} → {proposed}")

            if len(items) > 5:
                print(f"  ... and {len(items) - 5} more")

    def apply_folder_creation(self):
        """Apply folder creation recommendations"""
        print_header("CREATE RECOMMENDED FOLDERS")

        actions = self.index.get_pending_actions("create_folder")

        if not actions:
            print("\nNo folder creation actions pending.")
            print("Run analysis first to get recommendations.")
            return

        print(f"\nFolders to create: {len(actions)}")
        for a in actions[:20]:
            print(f"  📁 {a.get('proposed_value')}")

        confirm = input("\nCreate these folders? (yes/no): ").strip().lower()

        if confirm == 'yes':
            created = 0
            for a in actions:
                folder_path = self.root_path / a.get('proposed_value', '')
                try:
                    folder_path.mkdir(parents=True, exist_ok=True)
                    self.index.update_action_status(a['action_id'], 'applied')
                    created += 1
                except Exception as e:
                    print(f"  ❌ Failed: {folder_path}: {e}")

            print(f"\n✅ Created {created} folders")
        else:
            print("Cancelled.")

    def find_duplicates(self, min_copies: int = 2):
        """Find and optionally remove duplicate files"""
        print_header("FIND DUPLICATES")

        stats = self.index.get_statistics(root_path=self.root_path)
        duplicates = stats.get('potential_duplicates', [])

        if not duplicates:
            print("\nNo duplicates found.")
            return

        # Filter by minimum copies
        duplicates = [d for d in duplicates if d['count'] >= min_copies]

        # Calculate potential space savings
        total_wasted = 0

        print(f"\nFiles with {min_copies}+ copies:")
        print("-" * 60)

        for d in duplicates[:30]:
            name = d['name']
            count = d['count']

            # Get file sizes from index
            with sqlite3.connect(self.index.db_path) as conn:
                row = conn.execute(
                    "SELECT SUM(size) as total, size FROM files WHERE name = ? AND LOWER(path) LIKE LOWER(?)",
                    (name, str(self.root_path.resolve()).rstrip("\\/") + os.sep + "%"),
                ).fetchone()
                if row and row[0]:
                    total_size = row[0]
                    single_size = row[1] or 0
                    wasted = total_size - single_size
                    total_wasted += wasted
                    print(f"  {name}")
                    print(f"    {count} copies, {format_size(total_size)} total, {format_size(wasted)} wasted")

        if len(duplicates) > 30:
            print(f"\n  ... and {len(duplicates) - 30} more duplicate filenames")

        print(f"\n📊 Potential space savings: {format_size(total_wasted)}")
        print(f"   (if reduced to 1 copy each)")

        # Offer to export list
        export = input("\nExport full list to duplicates.csv? (yes/no): ").strip().lower()
        if export == 'yes':
            csv_path = self.db_dir / "duplicates.csv"
            with open(csv_path, 'w', encoding='utf-8') as f:
                f.write("filename,copies,folders\n")
                for d in duplicates:
                    folders = d.get('folders', '').replace('"', "'")
                    f.write(f'"{d["name"]}",{d["count"]},"{folders}"\n')
            print(f"✅ Exported to {csv_path}")

    def consolidate_duplicates(self, filename_pattern: str = None, min_copies: int = 2):
        """Move all but one copy of duplicate files to a consolidation folder"""
        print_header("CONSOLIDATE DUPLICATES")

        dest_folder = self.root_path / "_Duplicate_Files"

        with sqlite3.connect(self.index.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Find duplicates
            if filename_pattern:
                sql_pattern = filename_pattern.replace('*', '%').replace('?', '_')
                query = """
                    SELECT name, COUNT(*) as count
                    FROM files
                    WHERE name LIKE ?
                    GROUP BY name
                    HAVING count >= ?
                    ORDER BY count DESC
                """
                duplicates = conn.execute(query, (sql_pattern, min_copies)).fetchall()
            else:
                query = """
                    SELECT name, COUNT(*) as count
                    FROM files
                    GROUP BY name
                    HAVING count >= ?
                    ORDER BY count DESC
                """
                duplicates = conn.execute(query, (min_copies,)).fetchall()

            if not duplicates:
                print(f"\nNo duplicates found with {min_copies}+ copies.")
                return

            # Calculate totals
            total_files_to_move = 0
            total_size_to_move = 0

            print(f"\nDuplicates to consolidate:")
            print("-" * 50)

            for d in duplicates[:20]:
                name = d['name']
                count = d['count']

                # Get all copies
                copies = conn.execute(
                    "SELECT path, size FROM files WHERE name = ? ORDER BY modified DESC",
                    (name,)
                ).fetchall()

                # First one (newest) stays, rest move
                files_to_move = count - 1
                size_to_move = sum(c['size'] for c in copies[1:])

                total_files_to_move += files_to_move
                total_size_to_move += size_to_move

                print(f"  {name}: keep 1, move {files_to_move} ({format_size(size_to_move)})")

            if len(duplicates) > 20:
                # Calculate remaining
                for d in duplicates[20:]:
                    copies = conn.execute(
                        "SELECT size FROM files WHERE name = ?",
                        (d['name'],)
                    ).fetchall()
                    total_files_to_move += d['count'] - 1
                    total_size_to_move += sum(c['size'] for c in copies[1:])

                print(f"\n  ... and {len(duplicates) - 20} more duplicate filenames")

            print(f"\n📊 SUMMARY")
            print(f"   Unique filenames with duplicates: {len(duplicates)}")
            print(f"   Files to move: {total_files_to_move:,}")
            print(f"   Space to consolidate: {format_size(total_size_to_move)}")
            print(f"   Destination: {dest_folder}")

            confirm = input(f"\nMove {total_files_to_move:,} duplicate files? (yes/no): ").strip().lower()

            if confirm != 'yes':
                print("Cancelled.")
                return

            # Create destination
            dest_folder.mkdir(parents=True, exist_ok=True)

            moved = 0
            errors = 0
            skipped = 0

            print(f"\nMoving files...")

            for i, d in enumerate(duplicates):
                name = d['name']

                # Get all copies, sorted by modified date (newest first)
                copies = conn.execute(
                    "SELECT path, size, parent_folder FROM files WHERE name = ? ORDER BY modified DESC",
                    (name,)
                ).fetchall()

                # Keep the first (newest), move the rest
                for copy in copies[1:]:
                    src = Path(copy['path'])

                    if not src.exists():
                        skipped += 1
                        continue

                    # Create subfolder based on original location to avoid conflicts
                    # e.g., _Duplicate_Files/folder1_subfolder2/context.mdb
                    rel_folder = copy['parent_folder'].replace('/', '_').replace('\\', '_')
                    if rel_folder:
                        copy_dest = dest_folder / rel_folder
                    else:
                        copy_dest = dest_folder / "_root"

                    copy_dest.mkdir(parents=True, exist_ok=True)
                    dst = copy_dest / name

                    # Handle name conflicts
                    if dst.exists():
                        stem = Path(name).stem
                        suffix = Path(name).suffix
                        counter = 1
                        while dst.exists():
                            dst = copy_dest / f"{stem}_{counter}{suffix}"
                            counter += 1

                    try:
                        src.rename(dst)
                        moved += 1
                    except Exception as e:
                        errors += 1
                        if errors <= 5:
                            print(f"  ❌ Error moving {src}: {e}")

                # Progress every 100 filenames
                if (i + 1) % 100 == 0:
                    print(f"  Processed {i + 1}/{len(duplicates)} duplicate filenames...")

            print(f"\n✅ COMPLETE")
            print(f"   Moved: {moved:,} files")
            print(f"   Skipped (not found): {skipped:,}")
            print(f"   Errors: {errors:,}")
            print(f"   Destination: {dest_folder}")
            print(f"\n⚠️  Run 'Scan & Index' to update the database.")
            print(f"   Then review {dest_folder} and delete if not needed.")

    def find_by_pattern(self, pattern: str, silent: bool = False) -> List[Dict]:
        """
        Find files matching a pattern (supports glob-style patterns).

        Patterns:
        - *text* - filename contains 'text'
        - *.pdf - files with .pdf extension
        - folder/* - files in folder
        - folder/**/* - files recursively in folder
        - **/*text* - any file containing 'text' in path
        """
        if not silent:
            print_header(f"FILES MATCHING: {pattern}")

        with sqlite3.connect(self.index.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Normalize pattern - handle both / and \ separators
            pattern = pattern.replace('\\', '/')

            # Convert glob pattern to SQL LIKE
            # Handle different pattern types

            if pattern.startswith('**/'):
                # Recursive search anywhere: **/*text* -> path contains 'text'
                search_term = pattern[3:].replace('/*', '').replace('*', '%').replace('?', '_')
                # Also try with backslash for Windows paths
                query = """
                    SELECT path, name, extension, size, parent_folder
                    FROM files
                    WHERE (path LIKE ? OR path LIKE ? OR name LIKE ?)
                    ORDER BY parent_folder, name
                """
                params = (f'%{search_term}%', f'%{search_term.replace("/", chr(92))}%', f'%{search_term}%')

            elif '/**/' in pattern or '/**' in pattern:
                # folder/**/file or folder/** -> search in folder recursively
                parts = pattern.replace('/**', '/').split('/')
                folder_part = parts[0] if parts else ''
                file_part = parts[-1] if len(parts) > 1 and parts[-1] != '*' else '%'
                file_part = file_part.replace('*', '%')

                query = """
                    SELECT path, name, extension, size, parent_folder
                    FROM files
                    WHERE parent_folder LIKE ? AND name LIKE ?
                    ORDER BY parent_folder, name
                """
                # Search with folder name anywhere in path
                params = (f'%{folder_part}%', file_part)

            elif '/' in pattern:
                # Path-based pattern: folder/subfolder/*.pdf
                path_part = pattern.rsplit('/', 1)
                if len(path_part) == 2:
                    folder = path_part[0].replace('*', '%').replace('**', '%')
                    file = path_part[1].replace('*', '%')
                    query = """
                        SELECT path, name, extension, size, parent_folder
                        FROM files
                        WHERE parent_folder LIKE ? AND name LIKE ?
                        ORDER BY parent_folder, name
                    """
                    params = (f'%{folder}%', file)
                else:
                    sql_pattern = pattern.replace('*', '%').replace('?', '_')
                    query = """
                        SELECT path, name, extension, size, parent_folder
                        FROM files
                        WHERE path LIKE ?
                        ORDER BY parent_folder, name
                    """
                    params = (f'%{sql_pattern}%',)
            else:
                # Simple filename pattern
                sql_pattern = pattern.replace('*', '%').replace('?', '_')
                query = """
                    SELECT path, name, extension, size, parent_folder
                    FROM files
                    WHERE name LIKE ?
                    ORDER BY parent_folder, name
                """
                params = (sql_pattern,)

            rows = conn.execute(query + " LIMIT 500", params).fetchall()

            if not rows:
                if not silent:
                    print(f"\nNo files matching '{pattern}'")
                return []

            total_count = conn.execute(
                query.replace("SELECT path, name, extension, size, parent_folder", "SELECT COUNT(*)"),
                params
            ).fetchone()[0]

            if not silent:
                print(f"\nFound {total_count} files (showing first 100):")

                current_folder = None
                for r in rows[:100]:
                    if r['parent_folder'] != current_folder:
                        current_folder = r['parent_folder']
                        print(f"\n  📁 {current_folder or '(root)'}/")
                    print(f"      {r['name']} ({format_size(r['size'])})")

                if total_count > 100:
                    print(f"\n  ... and {total_count - 100} more files")

            return [dict(r) for r in rows]

    def move_files_by_pattern(self, pattern: str, destination: str) -> int:
        """Move files matching a pattern to a destination folder"""
        print(f"\n  Moving: {pattern} → {destination}")

        # Try multiple pattern interpretations
        files = self.find_by_pattern(pattern, silent=True)

        # If no matches, try extracting key terms
        if not files and '/' in pattern:
            # Extract folder names and try searching by those
            parts = pattern.replace('**/', '').replace('/*', '').replace('*', '').split('/')
            for part in parts:
                if part and len(part) > 2:
                    print(f"    Trying alternative pattern: *{part}*")
                    files = self.find_by_pattern(f"*{part}*", silent=True)
                    if files:
                        break

        if not files:
            print(f"    No files found matching '{pattern}'")
            return 0

        print(f"    Found {len(files)} files to move")

        dest_path = self.root_path / destination
        dest_path.mkdir(parents=True, exist_ok=True)

        moved = 0
        errors = 0
        not_found = 0

        for f in files:
            # Handle both absolute and relative paths
            src = Path(f['path'])
            if not src.is_absolute():
                src = self.root_path / f['path']

            # Also try with just the stored path if that doesn't work
            if not src.exists():
                src = self.root_path / f.get('parent_folder', '') / f['name']

            dst = dest_path / f['name']

            try:
                if src.exists():
                    # Handle duplicates
                    if dst.exists():
                        stem = dst.stem
                        suffix = dst.suffix
                        counter = 1
                        while dst.exists():
                            dst = dest_path / f"{stem}_{counter}{suffix}"
                            counter += 1

                    src.rename(dst)
                    moved += 1
                else:
                    not_found += 1
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"    ❌ {f['name']}: {e}")

        status = f"    ✓ Moved {moved} files"
        if not_found:
            status += f" ({not_found} not found - may have been moved already)"
        if errors:
            status += f" ({errors} errors)"
        print(status)
        return moved

    def _apply_rename_pattern(self, current_pattern: str, new_pattern: str) -> int:
        """Apply a rename pattern to matching files"""
        import re
        from datetime import datetime

        # Convert glob pattern to regex for matching
        regex_pattern = current_pattern.replace('*', '.*').replace('?', '.')

        # Find files that match the pattern
        files = self.find_by_pattern(current_pattern.replace('{', '*').replace('}', '*'), silent=True)

        if not files:
            print(f"    No files matching pattern")
            return 0

        renamed = 0
        for f in files:
            src = Path(f['path'])
            if not src.is_absolute():
                src = self.root_path / f['path']
            if not src.exists():
                src = self.root_path / f.get('parent_folder', '') / f['name']

            if not src.exists():
                continue

            # Build new name from pattern
            old_name = f['name']
            name_stem = src.stem
            name_ext = src.suffix

            # Replace template variables
            new_name = new_pattern
            new_name = new_name.replace('{ext}', name_ext.lstrip('.'))
            new_name = new_name.replace('{original_name}', name_stem)
            new_name = new_name.replace('{date}', datetime.now().strftime('%Y-%m-%d'))
            new_name = new_name.replace('{YYYY-MM-DD}', datetime.now().strftime('%Y-%m-%d'))

            # Handle (2), (3) version suffixes
            version_match = re.search(r'\((\d+)\)', old_name)
            if version_match:
                new_name = new_name.replace('_v2', f'_v{version_match.group(1)}')
                base_name = re.sub(r'\s*\(\d+\)', '', name_stem)
                new_name = new_name.replace('{original_name}', base_name)

            # Add extension if not present
            if not new_name.endswith(name_ext) and '{ext}' not in new_pattern:
                new_name = new_name + name_ext

            # Clean up template vars that couldn't be resolved
            new_name = re.sub(r'\{[^}]+\}', '', new_name)
            new_name = re.sub(r'_+', '_', new_name)  # Remove double underscores
            new_name = new_name.strip('_')

            if new_name and new_name != old_name:
                dst = src.parent / new_name
                try:
                    if not dst.exists():
                        src.rename(dst)
                        renamed += 1
                except Exception as e:
                    print(f"    ❌ {old_name}: {e}")

        if renamed:
            print(f"    ✓ Renamed {renamed} files")
        return renamed

    def move_by_extension(self, extension: str, destination: str):
        """Move all files with an extension to a destination folder"""
        print_header(f"MOVE {extension} FILES")

        with sqlite3.connect(self.index.db_path) as conn:
            conn.row_factory = sqlite3.Row

            rows = conn.execute("""
                SELECT path, name, size
                FROM files
                WHERE extension = ?
            """, (extension.lower(),)).fetchall()

            if not rows:
                print(f"\nNo {extension} files found.")
                return

            total_size = sum(r['size'] for r in rows)
            print(f"\nFound {len(rows)} {extension} files ({format_size(total_size)})")

            dest_path = self.root_path / destination
            print(f"Destination: {dest_path}")

            confirm = input(f"\nMove all {len(rows)} files? (yes/no): ").strip().lower()

            if confirm == 'yes':
                dest_path.mkdir(parents=True, exist_ok=True)
                moved = 0
                errors = 0

                for r in rows:
                    src = Path(r['path'])
                    dst = dest_path / r['name']

                    try:
                        if src.exists():
                            # Handle duplicates
                            if dst.exists():
                                stem = dst.stem
                                suffix = dst.suffix
                                counter = 1
                                while dst.exists():
                                    dst = dest_path / f"{stem}_{counter}{suffix}"
                                    counter += 1

                            src.rename(dst)
                            moved += 1
                    except Exception as e:
                        errors += 1
                        if errors <= 5:
                            print(f"  ❌ {r['name']}: {e}")

                print(f"\n✅ Moved {moved} files")
                if errors:
                    print(f"⚠️ {errors} errors")
                print("\nRun 'Scan & Index' to update the database.")
            else:
                print("Cancelled.")

    def execute_all_actions(self):
        """Execute all pending LLM-recommended actions with confirmation"""
        print_header("EXECUTE ALL RECOMMENDATIONS")

        actions = self.index.get_pending_actions()

        if not actions:
            print("\nNo pending actions. Run LLM Analysis (option 3) first.")
            return

        # Group by type
        by_type = {}
        for a in actions:
            t = a.get('action_type', 'unknown')
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(a)

        print(f"\nPending Actions Summary:")
        print("-" * 50)
        for action_type, items in by_type.items():
            print(f"  {action_type}: {len(items)} actions")
        print(f"\nTotal: {len(actions)} actions")

        print("\n" + "=" * 50)
        print("EXECUTION ORDER")
        print("=" * 50)
        print("1. Create new folders")
        print("2. Consolidate duplicates (keep 1, move rest)")
        print("3. Move files by pattern")
        print("4. Apply renames")
        print("5. Delete specified files/patterns")

        confirm = input("\nExecute all actions? (yes/no): ").strip().lower()

        if confirm not in ("yes", "y"):
            print("Cancelled.")
            return

        results = {
            "folders_created": 0,
            "files_moved": 0,
            "files_renamed": 0,
            "duplicates_consolidated": 0,
            "errors": []
        }

        # STEP 1: Create folders
        folder_types = ["create_folder", "create_folders", "create_directory"]
        folder_actions = []
        for ft in folder_types:
            if ft in by_type:
                folder_actions.extend(by_type[ft])

        if folder_actions:
            print("\n" + "-" * 40)
            print("STEP 1: Creating folders...")
            for action in folder_actions:
                folder_path = action.get('proposed_value', '')
                if folder_path:
                    full_path = self.root_path / folder_path
                    try:
                        full_path.mkdir(parents=True, exist_ok=True)
                        self.index.update_action_status(action['action_id'], 'applied')
                        results["folders_created"] += 1
                        print(f"  ✓ Created: {folder_path}")
                    except Exception as e:
                        results["errors"].append(f"Create folder {folder_path}: {e}")
            print(f"  Created {results['folders_created']} folders")

        # STEP 2: Handle duplicates (most space-saving action)
        dup_types = ["delete_files", "consolidate", "consolidate_duplicates", "deduplicate"]
        has_dup_actions = any(dt in by_type for dt in dup_types)
        if has_dup_actions:
            print("\n" + "-" * 40)
            print("STEP 2: Consolidating duplicates...")

            # Find all duplicates from index
            with sqlite3.connect(self.index.db_path) as conn:
                conn.row_factory = sqlite3.Row
                duplicates = conn.execute("""
                    SELECT name, COUNT(*) as count
                    FROM files
                    GROUP BY name
                    HAVING count > 1
                    ORDER BY count DESC
                """).fetchall()

            if duplicates:
                # Auto-consolidate context.mdb and other system files
                system_files = ['context.mdb', 'manifest.json', 'main.js', 'styles.css',
                               'data.json', 'theme.css', 'workspace.json']

                for dup in duplicates:
                    name = dup['name']
                    if name in system_files and dup['count'] > 5:
                        print(f"  Consolidating {name} ({dup['count']} copies)...")
                        self.consolidate_duplicates(filename_pattern=name, min_copies=2)
                        results["duplicates_consolidated"] += dup['count'] - 1

        # STEP 3: Move files (file-level first, then patterns)
        file_move_actions = by_type.get("move_file", []) + by_type.get("rename_file", [])
        move_types = ["move_pattern", "move", "move_files", "relocate", "reorganize", "reorganize_by_year", "archive"]
        move_actions = []
        for move_type in move_types:
            if move_type in by_type:
                move_actions.extend(by_type[move_type])

        if file_move_actions or move_actions:
            print("\n" + "-" * 40)
            print("STEP 3: Moving files...")

        if file_move_actions:
            for action in file_move_actions:
                current = action.get('current_value', '') or action.get('path', '')
                proposed = action.get('proposed_value', '')
                if not current or not proposed:
                    continue

                src = Path(current)
                if not src.is_absolute():
                    src = self.root_path / current

                dst = Path(proposed)
                if not dst.is_absolute():
                    dst = self.root_path / proposed

                if dst.is_dir():
                    dst = dst / src.name

                if not src.exists():
                    results["errors"].append(f"Missing source: {src}")
                    continue

                # Avoid overwrite
                if dst.exists():
                    base = dst.stem
                    suffix = dst.suffix
                    counter = 1
                    while dst.exists():
                        dst = dst.with_name(f"{base}_{counter}{suffix}")
                        counter += 1

                try:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    src.rename(dst)
                    results["files_moved"] += 1
                    self.index.update_action_status(action['action_id'], 'applied')
                except Exception as e:
                    results["errors"].append(f"Move {src} → {dst}: {e}")

        if move_actions:
            print("\n  Pattern-based moves...")
            for action in move_actions:
                current = action.get('current_value', '')
                destination = action.get('proposed_value', '')

                # Handle different field names from LLM
                if not current:
                    current = action.get('from_pattern', action.get('source', action.get('from', '')))
                if not destination:
                    destination = action.get('to', action.get('target', action.get('destination', '')))

                if current and destination:
                    print(f"\n  Moving: {current} → {destination}")
                    moved = self.move_files_by_pattern(current, destination)
                    results["files_moved"] += moved
                    self.index.update_action_status(action['action_id'], 'applied')

        # STEP 4: Rename files
        rename_types = ["rename_pattern", "rename", "rename_files"]
        rename_actions = []
        for rename_type in rename_types:
            if rename_type in by_type:
                rename_actions.extend(by_type[rename_type])

        if rename_actions:
            print("\n" + "-" * 40)
            print("STEP 4: Renaming files...")

            for action in rename_actions:
                current = action.get('current_value', action.get('current_pattern', ''))
                new = action.get('proposed_value', action.get('new_pattern', ''))
                print(f"  Pattern: {current} → {new}")

                # Try to apply the rename pattern
                renamed = self._apply_rename_pattern(current, new)
                results["files_renamed"] = results.get("files_renamed", 0) + renamed
                self.index.update_action_status(action['action_id'], 'applied')

        # Summary
        print("\n" + "=" * 50)
        print("EXECUTION COMPLETE")
        print("=" * 50)
        print(f"  Folders created: {results['folders_created']}")
        print(f"  Files moved: {results['files_moved']}")
        print(f"  Files renamed: {results.get('files_renamed', 0)}")
        print(f"  Duplicates consolidated: {results['duplicates_consolidated']}")

        if results["errors"]:
            print(f"\n  Errors ({len(results['errors'])}):")
            for err in results["errors"][:10]:
                print(f"    ⚠️ {err}")
            if len(results["errors"]) > 10:
                print(f"    ... and {len(results['errors']) - 10} more")

        print("\n⚠️  Run 'Scan & Index' (option 1) to update the database!")

    def smart_organize(self):
        """One-click: Analyze + Execute recommendations"""
        print_header("SMART AUTO-ORGANIZE")
        print("This will:")
        print("  1. Send indexed data to LLM for analysis")
        print("  2. Review recommendations with you")
        print("  3. Execute approved actions")

        confirm = input("\nProceed? (yes/no): ").strip().lower()
        if confirm not in ("yes", "y"):
            print("Cancelled.")
            return

        # Step 1: Analyze
        print("\n" + "-" * 40)
        print("Analyzing with LLM...")
        recommendations = self.analyze()

        if not recommendations:
            print("Analysis failed or returned no recommendations.")
            return

        # Step 2: Review
        print("\n" + "-" * 40)
        proceed = input("\nExecute these recommendations? (yes/no): ").strip().lower()

        if proceed in ("yes", "y"):
            self.execute_all_actions()
        else:
            print("You can execute later with menu option 12.")

    def smart_cleanup(self):
        """Direct rule-based cleanup - no LLM, just concrete actions"""
        print_header("SMART CLEANUP (Rule-Based)")
        print("This performs concrete file organization WITHOUT LLM:")
        print()
        print("  1. Move icon files (EPS/small PNG) → Assets/Icons")
        print("  2. Sort loose files by document type entity")
        print("  3. Move files by extension to appropriate folders")
        print("  4. Clean up folder roots (move loose files to subfolders)")
        print()

        confirm = input("Proceed? (yes/no): ").strip().lower()
        if confirm not in ("yes", "y"):
            print("Cancelled.")
            return

        results = {
            "icons_moved": 0,
            "files_sorted": 0,
            "folders_cleaned": 0,
            "errors": []
        }

        # STEP 1: Move icon files (EPS and small PNG files)
        print("\n" + "-" * 40)
        print("STEP 1: Moving icon files...")

        icon_dest = self.root_path / "Assets" / "Icons"
        icon_dest.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.index.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Find EPS files and small PNG files (likely icons)
            icon_files = conn.execute("""
                SELECT path, name, size, parent_folder
                FROM files
                WHERE extension = '.eps'
                   OR (extension = '.png' AND size < 50000)
                   OR name LIKE '%-icon%'
                   OR name LIKE '%_icon%'
                   OR parent_folder LIKE '%icon%'
            """).fetchall()

            for f in icon_files:
                src = Path(f['path'])
                if not src.is_absolute():
                    src = self.root_path / f['path']
                if not src.exists():
                    src = self.root_path / f['parent_folder'] / f['name'] if f['parent_folder'] else self.root_path / f['name']

                if src.exists() and 'Assets' not in str(src):
                    dst = icon_dest / f['name']
                    if dst.exists():
                        dst = icon_dest / f"{src.stem}_{results['icons_moved']}{src.suffix}"
                    try:
                        src.rename(dst)
                        results["icons_moved"] += 1
                    except Exception as e:
                        results["errors"].append(f"Icon {f['name']}: {e}")

        print(f"  ✓ Moved {results['icons_moved']} icon files to Assets/Icons")

        # STEP 2: Sort files by document type
        print("\n" + "-" * 40)
        print("STEP 2: Sorting files by document type...")

        doc_type_folders = {
            'motion': 'Motions',
            'order': 'Orders',
            'complaint': 'Complaints',
            'affidavit': 'Affidavits',
            'subpoena': 'Subpoenas',
            'exhibit': 'Exhibits',
            'discovery': 'Discovery',
            'brief': 'Filings',
            'petition': 'Complaints',
            'notice': 'Orders',
            'warrant': 'Orders',
            'deposition': 'Discovery',
            'interrogator': 'Discovery',
            'pleading': 'Filings',
        }

        with sqlite3.connect(self.index.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Find files with doc_type entities that are in wrong folders
            files_with_doctype = conn.execute("""
                SELECT f.path, f.name, f.parent_folder, fe.entity_value as doc_type
                FROM files f
                JOIN file_entities fe ON f.file_id = fe.file_id
                WHERE fe.entity_type = 'doc_type'
                  AND f.extension IN ('.pdf', '.docx', '.doc', '.md', '.txt')
            """).fetchall()

            for f in files_with_doctype:
                doc_type = f['doc_type'].lower()
                target_folder = doc_type_folders.get(doc_type)

                if not target_folder:
                    continue

                # Check if file is already in the right folder
                current_folder = f['parent_folder'] or ''
                if target_folder.lower() in current_folder.lower():
                    continue

                # Find the best destination - look for existing folder structure
                src = Path(f['path'])
                if not src.is_absolute():
                    src = self.root_path / f['path']
                if not src.exists():
                    src = self.root_path / current_folder / f['name'] if current_folder else self.root_path / f['name']

                if not src.exists():
                    continue

                # Try to find existing target folder in parent structure
                dest_base = src.parent
                while dest_base != self.root_path and dest_base.parent != dest_base:
                    potential_dest = dest_base / target_folder
                    if potential_dest.exists():
                        break
                    dest_base = dest_base.parent
                else:
                    # Create at same level as source
                    dest_base = src.parent

                dest_folder = dest_base / target_folder
                dest_folder.mkdir(parents=True, exist_ok=True)

                dst = dest_folder / f['name']
                if dst.exists():
                    continue  # Don't overwrite

                try:
                    src.rename(dst)
                    results["files_sorted"] += 1
                except Exception as e:
                    results["errors"].append(f"Sort {f['name']}: {e}")

        print(f"  ✓ Sorted {results['files_sorted']} files by document type")

        # STEP 3: Clean up folder roots - move loose text files
        print("\n" + "-" * 40)
        print("STEP 3: Cleaning up folder roots...")

        with sqlite3.connect(self.index.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Find folders with loose files AND subfolders
            folders_to_clean = conn.execute("""
                SELECT parent_folder, COUNT(*) as file_count
                FROM files
                WHERE parent_folder != '' AND parent_folder IS NOT NULL
                GROUP BY parent_folder
                HAVING file_count > 10
            """).fetchall()

            for folder_info in folders_to_clean:
                folder_path = self.root_path / folder_info['parent_folder']

                if not folder_path.exists():
                    continue

                # Check if folder has subfolders
                subfolders = [d for d in folder_path.iterdir() if d.is_dir()]
                if not subfolders:
                    continue

                # Get loose files at this level
                loose_files = [f for f in folder_path.iterdir() if f.is_file()]

                if len(loose_files) < 5:
                    continue

                # Create "Unsorted" or use existing subfolder logic
                unsorted_folder = folder_path / "_Unsorted"

                for f in loose_files:
                    # Try to determine appropriate subfolder from filename
                    name_lower = f.name.lower()
                    moved = False

                    for doc_type, target in doc_type_folders.items():
                        if doc_type in name_lower:
                            dest = folder_path / target
                            if dest.exists() or any(target.lower() in sf.name.lower() for sf in subfolders):
                                # Find matching subfolder
                                for sf in subfolders:
                                    if target.lower() in sf.name.lower():
                                        dest = sf
                                        break
                                else:
                                    dest.mkdir(exist_ok=True)

                                dst = dest / f.name
                                if not dst.exists():
                                    try:
                                        f.rename(dst)
                                        results["folders_cleaned"] += 1
                                        moved = True
                                    except:
                                        pass
                                break

                    if not moved and f.suffix.lower() in ['.txt', '.md']:
                        # Move unmatched text files to Unsorted
                        unsorted_folder.mkdir(exist_ok=True)
                        dst = unsorted_folder / f.name
                        if not dst.exists():
                            try:
                                f.rename(dst)
                                results["folders_cleaned"] += 1
                            except:
                                pass

        print(f"  ✓ Cleaned {results['folders_cleaned']} files from folder roots")

        # STEP 4: Rename poor quality filenames
        print("\n" + "-" * 40)
        print("STEP 4: Fixing poor quality filenames...")

        results["files_renamed"] = 0

        with sqlite3.connect(self.index.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Find files with poor quality scores and suggested names
            poor_files = conn.execute("""
                SELECT path, name, parent_folder, quality_score, suggested_name, doc_type
                FROM files
                WHERE quality_score < 0.4
                  AND suggested_name IS NOT NULL
                  AND suggested_name != ''
                  AND extension IN ('.pdf', '.docx', '.doc', '.txt', '.md')
                ORDER BY quality_score ASC
                LIMIT 100
            """).fetchall()

            if poor_files:
                print(f"  Found {len(poor_files)} files with poor names")

                for f in poor_files:
                    src = Path(f['path'])
                    if not src.is_absolute():
                        src = self.root_path / f['path']
                    if not src.exists():
                        src = self.root_path / f['parent_folder'] / f['name'] if f['parent_folder'] else self.root_path / f['name']

                    if not src.exists():
                        continue

                    suggested = f['suggested_name']
                    dst = src.parent / suggested

                    # Don't overwrite existing files
                    if dst.exists():
                        continue

                    try:
                        src.rename(dst)
                        results["files_renamed"] += 1
                        if results["files_renamed"] <= 5:
                            print(f"    {f['name'][:40]}... → {suggested[:40]}...")
                    except Exception as e:
                        results["errors"].append(f"Rename {f['name']}: {e}")

                if results["files_renamed"] > 5:
                    print(f"    ... and {results['files_renamed'] - 5} more")
            else:
                print("  No files need renaming (or run Scan first to detect them)")

        print(f"  ✓ Renamed {results['files_renamed']} files with better names")

        # Summary
        print("\n" + "=" * 50)
        print("SMART CLEANUP COMPLETE")
        print("=" * 50)
        print(f"  Icons moved: {results['icons_moved']}")
        print(f"  Files sorted by type: {results['files_sorted']}")
        print(f"  Folder roots cleaned: {results['folders_cleaned']}")
        print(f"  Files renamed: {results['files_renamed']}")

        total = results['icons_moved'] + results['files_sorted'] + results['folders_cleaned'] + results['files_renamed']
        print(f"\n  TOTAL FILES ORGANIZED: {total}")

        if results["errors"]:
            print(f"\n  Errors ({len(results['errors'])}):")
            for err in results["errors"][:5]:
                print(f"    ⚠️ {err}")

        print("\n⚠️  Run 'Scan & Index' (option 1) to update the database!")

    def show_poor_filenames(self):
        """Show files with poor quality names and suggest better ones"""
        print_header("POOR QUALITY FILENAMES")

        with sqlite3.connect(self.index.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Check if quality_score column exists
            cursor = conn.execute("PRAGMA table_info(files)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'quality_score' not in columns:
                print("\n⚠️  Quality scores not available.")
                print("   Run 'Scan & Index' (option 1) first to analyze filenames.")
                return

            # Find poor quality files
            poor_files = conn.execute("""
                SELECT path, name, parent_folder, quality_score, suggested_name, doc_type, extension
                FROM files
                WHERE quality_score IS NOT NULL
                ORDER BY quality_score ASC
                LIMIT 50
            """).fetchall()

            if not poor_files:
                print("\nNo files found. Run 'Scan & Index' first.")
                return

            # Show statistics
            stats = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN quality_score < 0.3 THEN 1 ELSE 0 END) as very_poor,
                    SUM(CASE WHEN quality_score >= 0.3 AND quality_score < 0.5 THEN 1 ELSE 0 END) as poor,
                    SUM(CASE WHEN quality_score >= 0.5 AND quality_score < 0.7 THEN 1 ELSE 0 END) as ok,
                    SUM(CASE WHEN quality_score >= 0.7 THEN 1 ELSE 0 END) as good,
                    SUM(CASE WHEN suggested_name IS NOT NULL THEN 1 ELSE 0 END) as has_suggestion
                FROM files
                WHERE quality_score IS NOT NULL
            """).fetchone()

            print("\nFILENAME QUALITY DISTRIBUTION")
            print("-" * 40)
            print(f"  🔴 Very Poor (< 0.3): {stats['very_poor'] or 0}")
            print(f"  🟠 Poor (0.3 - 0.5):  {stats['poor'] or 0}")
            print(f"  🟡 OK (0.5 - 0.7):    {stats['ok'] or 0}")
            print(f"  🟢 Good (> 0.7):      {stats['good'] or 0}")
            print(f"\n  Files with auto-suggestions: {stats['has_suggestion'] or 0}")

            print("\n\nWORST FILENAMES (showing 20):")
            print("-" * 70)

            for f in poor_files[:20]:
                score = f['quality_score'] or 0
                icon = "🔴" if score < 0.3 else "🟠" if score < 0.5 else "🟡"

                print(f"\n{icon} {f['name'][:50]}")
                print(f"   Score: {score:.2f} | Type: {f['doc_type'] or 'unknown'}")
                print(f"   Folder: {f['parent_folder'] or '(root)'}")

                if f['suggested_name']:
                    print(f"   ➡️  Suggested: {f['suggested_name'][:50]}")

            # Offer to apply suggestions
            print("\n" + "=" * 50)
            apply = input("\nApply suggested renames? (yes/no): ").strip().lower()

            if apply == 'yes':
                # Get files with suggestions
                to_rename = conn.execute("""
                    SELECT path, name, parent_folder, suggested_name
                    FROM files
                    WHERE quality_score < 0.5
                      AND suggested_name IS NOT NULL
                      AND suggested_name != ''
                """).fetchall()

                renamed = 0
                errors = 0

                for f in to_rename:
                    src = Path(f['path'])
                    if not src.is_absolute():
                        src = self.root_path / f['path']
                    if not src.exists():
                        src = self.root_path / f['parent_folder'] / f['name'] if f['parent_folder'] else self.root_path / f['name']

                    if not src.exists():
                        continue

                    dst = src.parent / f['suggested_name']

                    if dst.exists():
                        continue

                    try:
                        src.rename(dst)
                        renamed += 1
                    except Exception:
                        errors += 1

                print(f"\n✅ Renamed {renamed} files")
                if errors:
                    print(f"⚠️  {errors} errors")
                print("\nRun 'Scan & Index' to update the database!")

    def find_all_duplicates_enhanced(self):
        """Find duplicates using enhanced detection (4 types)"""
        print_header("ENHANCED DUPLICATE DETECTION")

        try:
            # Import enhanced organizer
            import sys
            sys.path.insert(0, str(Path(__file__).parent / "src"))
            from file_organizer.integration import EnhancedFileOrganizer

            print("Initializing enhanced duplicate detector...")
            db_path = self.db_dir / "enhanced_organizer.db"
            enhanced = EnhancedFileOrganizer(db_path=db_path)

            print("\nRunning comprehensive duplicate detection...")
            print("(This may take a few minutes for large collections)")

            results = enhanced.find_all_duplicates()

            print(f"\n{'=' * 60}")
            print("DUPLICATE DETECTION RESULTS")
            print("=" * 60)

            print(f"\n📊 Summary:")
            print(f"  Total duplicate groups found: {results['total_duplicate_groups']}")
            print(f"  - Exact duplicates: {len(results['exact_duplicates'])} groups")
            print(f"  - Content duplicates: {len(results['content_duplicates'])} groups")
            print(f"  - Perceptual duplicates: {len(results['perceptual_duplicates'])} groups")
            print(f"  - Semantic duplicates: {len(results['semantic_duplicates'])} groups")

            # Show examples
            if results['exact_duplicates']:
                print(f"\n📋 Exact Duplicate Groups (first 5):")
                for i, group in enumerate(results['exact_duplicates'][:5], 1):
                    print(f"\n  Group {i} ({group['count']} files):")
                    for fid in group['files'][:3]:
                        print(f"    • {fid}")
                    if group['count'] > 3:
                        print(f"    ... and {group['count'] - 3} more")

            if results['semantic_duplicates']:
                print(f"\n🧠 Semantic Duplicate Groups (similar content):")
                for i, group in enumerate(results['semantic_duplicates'][:3], 1):
                    print(f"\n  Group {i} ({group['count']} files):")
                    for fid in group['files'][:3]:
                        print(f"    • {fid}")

            print(f"\n💡 Tip: Use option 10 to consolidate exact duplicates")

            enhanced.close()

        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Make sure enhanced features are installed:")
            print("  pip install sentence-transformers scikit-learn numpy imagehash pillow")

    def cluster_documents_interactive(self):
        """Cluster documents by semantic similarity"""
        print_header("DOCUMENT CLUSTERING")

        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent / "src"))
            from file_organizer.integration import EnhancedFileOrganizer

            db_path = self.db_dir / "enhanced_organizer.db"
            enhanced = EnhancedFileOrganizer(db_path=db_path)

            n_clusters = input("\nNumber of clusters to create (default 5): ").strip()
            n_clusters = int(n_clusters) if n_clusters else 5

            print(f"\nClustering documents into {n_clusters} groups...")
            print("(This requires documents with embeddings)")

            clusters = enhanced.cluster_similar_documents(n_clusters=n_clusters)

            if not clusters:
                print("\n⚠️  No documents with embeddings found.")
                print("Run option 21 first to process files and generate embeddings.")
            else:
                print(f"\n{'=' * 60}")
                print(f"CLUSTERING RESULTS - {len(clusters)} Clusters Created")
                print("=" * 60)

                for cluster in clusters:
                    print(f"\n📁 {cluster['cluster_name']}")
                    print(f"   Files: {cluster['file_count']}")
                    print(f"   Avg Similarity: {cluster['avg_similarity']:.1%}")
                    print(f"   Members:")
                    for fid in cluster['files'][:5]:
                        print(f"     • {fid}")
                    if cluster['file_count'] > 5:
                        print(f"     ... and {cluster['file_count'] - 5} more")

                print(f"\n💡 These clusters represent semantically similar documents")
                print("   Consider organizing them into the same folders")

            enhanced.close()

        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()

    def validate_quality_interactive(self):
        """Validate organization quality"""
        print_header("QUALITY VALIDATION")

        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent / "src"))
            from file_organizer.integration import EnhancedFileOrganizer

            db_path = self.db_dir / "enhanced_organizer.db"
            enhanced = EnhancedFileOrganizer(db_path=db_path)

            if not enhanced.quality_validator:
                print("❌ Quality validator not available")
                return

            print("\nGenerating quality report...")
            report = enhanced.quality_validator.generate_quality_report()

            print(f"\n{'=' * 60}")
            print("ORGANIZATION QUALITY REPORT")
            print("=" * 60)

            stats = report.get('overall_statistics', {})
            print(f"\n📊 Overall Statistics:")
            print(f"  Files analyzed: {stats.get('total_files', 0):,}")
            print(f"  Avg organization score: {stats.get('avg_org_score', 0):.1%}")
            print(f"  Avg content score: {stats.get('avg_content_score', 0):.1%}")
            print(f"  Avg naming score: {stats.get('avg_naming_score', 0):.1%}")
            print(f"  Avg metadata score: {stats.get('avg_metadata_score', 0):.1%}")

            print(f"\n⚠️  Issues Found: {report.get('files_with_issues', 0)} files")

            if report.get('top_issues'):
                print(f"\n🔍 Top Issues:")
                for issue_type, count in report['top_issues'][:5]:
                    print(f"  • {issue_type}: {count} occurrences")

            if report.get('recommendations'):
                print(f"\n💡 Recommendations:")
                for rec in report['recommendations']:
                    print(f"  • {rec}")

            enhanced.close()

        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()

    def show_learning_analytics(self):
        """Show user feedback and learning analytics"""
        print_header("LEARNING ANALYTICS")

        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent / "src"))
            from file_organizer.integration import EnhancedFileOrganizer

            db_path = self.db_dir / "enhanced_organizer.db"
            enhanced = EnhancedFileOrganizer(db_path=db_path)

            if not enhanced.feedback_tracker:
                print("❌ Feedback tracker not available")
                return

            days = input("\nAnalyze last N days (default 30): ").strip()
            days = int(days) if days else 30

            print(f"\nAnalyzing feedback from last {days} days...")
            analytics = enhanced.feedback_tracker.generate_feedback_analytics(days=days)

            print(f"\n{'=' * 60}")
            print(f"USER FEEDBACK ANALYTICS - Last {days} Days")
            print("=" * 60)

            print(f"\n📊 Summary:")
            print(f"  Total corrections: {analytics['total_corrections']}")
            print(f"  Correction rate: {analytics['correction_rate']:.1f}/day")
            print(f"  Preferences learned: {analytics['preferences_learned']}")
            print(f"  Accuracy improvement: {analytics['accuracy_improvement']:.1%}")

            print(f"\n📈 Corrections by Type:")
            for corr_type, count in analytics['corrections_by_type'].items():
                print(f"  {corr_type}: {count}")

            print(f"\n⚠️  High-confidence errors: {analytics['high_confidence_errors']}")
            print("    (System was confident but user corrected)")

            if analytics['most_corrected_patterns']:
                print(f"\n🔍 Most Corrected Patterns:")
                for pattern in analytics['most_corrected_patterns'][:5]:
                    print(f"  • {pattern['pattern']}: {pattern['count']} times")

            # Show learned preferences
            preferences = enhanced.feedback_tracker.get_preferences(min_strength=0.5)
            if preferences:
                print(f"\n🎯 Strong Preferences Learned ({len(preferences)}):")
                for pref in preferences[:5]:
                    print(f"  • {pref.preference_type}/{pref.preference_key}: {pref.preference_value}")
                    print(f"    Strength: {pref.strength:.1%} (from {pref.learned_from_corrections} corrections)")

            enhanced.close()

        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()

    def generate_comprehensive_report(self):
        """Generate comprehensive organization report"""
        print_header("COMPREHENSIVE REPORT")

        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent / "src"))
            from file_organizer.integration import EnhancedFileOrganizer

            db_path = self.db_dir / "enhanced_organizer.db"
            enhanced = EnhancedFileOrganizer(db_path=db_path)

            print("\nGenerating comprehensive report...")
            print("(This may take a moment)")

            report = enhanced.generate_comprehensive_report()

            print(f"\n{'=' * 60}")
            print("COMPREHENSIVE ORGANIZATION REPORT")
            print("=" * 60)

            print(f"\nGenerated: {report['timestamp']}")
            print(f"Database: {report['database']}")
            print(f"User: {report['user_id']}")

            # Database stats
            if 'database_stats' in report:
                print(f"\n📊 Database Statistics:")
                stats = report['database_stats']
                print(f"  Files indexed: {stats.get('files_count', 0):,}")
                print(f"  Content cached: {stats.get('content_cache_count', 0):,}")
                print(f"  Embeddings generated: {stats.get('document_embeddings_count', 0):,}")
                print(f"  Duplicates tracked: {stats.get('duplicates_count', 0):,}")
                print(f"  Quality metrics: {stats.get('quality_metrics_count', 0):,}")
                print(f"  User corrections: {stats.get('user_corrections_count', 0):,}")

            # Quality
            if 'quality' in report:
                quality = report['quality']
                stats = quality.get('overall_statistics', {})
                print(f"\n✅ Quality Metrics:")
                print(f"  Avg organization: {stats.get('avg_org_score', 0):.1%}")
                print(f"  Avg naming: {stats.get('avg_naming_score', 0):.1%}")
                print(f"  Files with issues: {quality.get('files_with_issues', 0)}")

            # Feedback
            if 'feedback' in report:
                feedback = report['feedback']
                print(f"\n📈 Learning & Feedback:")
                print(f"  Corrections (30 days): {feedback.get('total_corrections', 0)}")
                print(f"  Correction rate: {feedback.get('correction_rate', 0):.1f}/day")
                print(f"  Accuracy improvement: {feedback.get('accuracy_improvement', 0):.1%}")

            # Duplicates
            if 'duplicates' in report:
                dups = report['duplicates']
                print(f"\n🔍 Duplicates:")
                print(f"  Duplicate groups: {dups.get('total_groups', 0)}")
                print(f"  Total duplicate files: {dups.get('total_files', 0)}")

            # Clustering
            if 'clustering' in report:
                clustering = report['clustering']
                print(f"\n🧩 Clustering:")
                print(f"  Document clusters: {clustering.get('total_clusters', 0)}")

            print(f"\n💡 This comprehensive report combines all enhanced features")
            print("   Run individual tools (16-21) for detailed analysis")

            enhanced.close()

        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()

    def process_files_comprehensive_interactive(self):
        """Process files with all enhanced features - optimized for large datasets"""
        print_header("COMPREHENSIVE FILE PROCESSING")

        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent / "src"))
            from file_organizer.integration import EnhancedFileOrganizer

            db_path = self.db_dir / "enhanced_organizer.db"
            enhanced = EnhancedFileOrganizer(db_path=db_path)

            print("\nThis will process files with:")
            print("  ✓ Content extraction & caching")
            print("  ✓ Embedding generation (for similarity)")
            print("  ✓ Hash calculation (for duplicates)")
            print("  ✓ Quality validation")

            limit = input("\nProcess how many files? (default 10): ").strip()
            limit = int(limit) if limit else 10

            # For large datasets, use batching to prevent memory issues
            batch_size = 25 if limit > 100 else (10 if limit > 50 else 5)
            print(f"Using batch size: {batch_size} (to prevent memory issues)")
            auto_continue = input("\nAuto-continue all batches? (y/n, default y): ").strip().lower()
            auto_continue = (auto_continue in ("y", "yes", ""))

            # Get files from index
            stats = self.index.get_statistics()

            # Get file paths from database
            import sqlite3
            conn = sqlite3.connect(self.db_dir / "file_index.db")
            cursor = conn.cursor()
            root_prefix = str(self.root_path.resolve()).rstrip("\\/") + os.sep + "%"
            cursor.execute(
                "SELECT file_id, path FROM files WHERE LOWER(path) LIKE LOWER(?) LIMIT ?",
                (root_prefix, limit),
            )
            files = cursor.fetchall()
            conn.close()

            if not files:
                print("\n⚠️  No files in index. Run 'Scan & Index' first.")
                return

            print(f"\nProcessing {len(files)} files in batches of {batch_size}...")

            processed = 0
            errors = 0

            for i in range(0, len(files), batch_size):
                batch = files[i:i + batch_size]
                batch_num = i//batch_size + 1
                total_batches = (len(files) + batch_size - 1)//batch_size
                print(f"\n--- Batch {batch_num}/{total_batches} ---")

                for file_id, file_path in batch:
                    try:
                        result = enhanced.process_file_comprehensive(
                            file_id=file_id,
                            file_path=Path(file_path),
                            extract_content=True,
                            generate_embedding=True,
                            calculate_hashes=True,
                            validate_quality=True
                        )

                        print(f"✓ {Path(file_path).name}")
                        print(f"  Content: {'✓' if result['content_extracted'] else '✗'}")
                        print(f"  Embedding: {'✓' if result['embedding_generated'] else '✗'}")
                        print(f"  Hashes: {'✓' if result['hashes_calculated'] else '✗'}")
                        print(f"  Quality: {result.get('quality_score', 0):.1f}")

                        processed += 1

                    except Exception as e:
                        print(f"✗ {Path(file_path).name}: {str(e)[:100]}...")
                        errors += 1

                # Progress update every 100 files
                if processed % 100 == 0 and processed > 0:
                    print(f"\n--- Progress: {processed}/{len(files)} files processed ---")

                # Force garbage collection between batches
                import gc
                gc.collect()

                # Clear model cache if similarity engine is available
                if hasattr(enhanced, 'similarity_engine') and enhanced.similarity_engine:
                    enhanced.similarity_engine.clear_memory_cache()

                # Optional pause between batches for very large processing
                if not auto_continue and len(files) > 500 and (i + batch_size) < len(files):
                    response = input(f"\nBatch {batch_num} complete. Continue? (y/n): ").strip().lower()
                    if response not in ("y", "yes", ""):
                        print("Processing paused by user.")
                        break

            print(f"\n{'=' * 60}")
            print(f"PROCESSING COMPLETE")
            print(f"  Processed: {processed}")
            print(f"  Errors: {errors}")
            print(f"  Success rate: {(processed/(processed+errors)*100):.1f}%" if processed+errors > 0 else "N/A")
            print("=" * 60)

            print("\n💡 Now you can:")
            print("  • Find duplicates (option 15)")
            print("  • Cluster similar documents (option 16)")
            print("  • Validate quality (option 17)")

            enhanced.close()

        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()

    def show_recommended_workflows(self):
        """Show recommended workflows for different use cases"""
        print_header("RECOMMENDED WORKFLOWS")

        print("""
╔═══════════════════════════════════════════════════════════════╗
║                    RECOMMENDED WORKFLOWS                       ║
╚═══════════════════════════════════════════════════════════════╝

🎯 WORKFLOW 1: Complete Organization (First-Time Setup)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Purpose: Fully organize a messy folder for the first time

Steps:
  1. Scan & Index Files (option 1)
     → Fast regex-based indexing of all files

  2. Process Files Comprehensively (option 21)
     → Extract content, generate embeddings, calculate hashes

  3. Find All Duplicates (option 16)
     → Detect exact, content, perceptual, and semantic duplicates

  4. Consolidate Duplicates (option 10)
     → Remove duplicate files, keep best copies

  5. LLM Analyze Structure (option 3)
     → Let AI analyze and suggest organization

  6. Validate Quality (option 18)
     → Check organization quality, get recommendations

  7. Execute All Recommendations (option 7)
     → Apply AI suggestions

  8. Generate Report (option 20)
     → Get comprehensive analysis

Time: 30-60 minutes for 1000+ files
Result: Fully organized, deduplicated folder with quality metrics

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚀 WORKFLOW 2: Quick Smart Organization (Fast Path)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Purpose: Quickly organize files with AI assistance

Steps:
  1. Scan & Index Files (option 1)
  2. Smart Auto-Organize (option 8)
     → Analyze + Execute in one step
  3. Smart Cleanup (option 14)
     → Rule-based cleanup (temp files, etc.)

Time: 5-10 minutes for 1000+ files
Result: Good organization without manual intervention

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍 WORKFLOW 3: Duplicate Detection & Cleanup
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Purpose: Find and remove duplicate files

Steps:
  1. Scan & Index Files (option 1)

  2. Process Files (calculate hashes) (option 21)
     → Just answer "yes" for hashes, "no" for others if speed matters

  3. Find All Duplicates (option 16)
     → 4 types: exact, content, perceptual, semantic

  4. Review duplicates and consolidate (option 10)
     → Keeps best copy, moves rest to _Duplicate_Files/

Time: 10-20 minutes
Result: Duplicate-free file collection

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🧩 WORKFLOW 4: Content-Based Organization
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Purpose: Organize by document content/meaning

Steps:
  1. Scan & Index Files (option 1)

  2. Process Files (extract + embed) (option 21)
     → Generate embeddings for semantic understanding

  3. Cluster Similar Documents (option 17)
     → Group by semantic similarity (5-10 clusters typical)

  4. Create folders based on clusters
     → Use cluster names as folder names

  5. Move files into cluster-based folders
     → Manual or via option 12

Time: 20-30 minutes
Result: Content-aware organization

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 WORKFLOW 5: Quality Assessment & Improvement
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Purpose: Assess and improve existing organization

Steps:
  1. Scan & Index Files (option 1)

  2. Validate Organization Quality (option 18)
     → Get 4D quality scores and issues

  3. Fix Poor Filenames (option 15)
     → Address naming issues

  4. Review misclassified files
     → Check quality report recommendations

  5. Re-validate (option 18)
     → Measure improvement

Time: 15-25 minutes
Result: Quality metrics and actionable improvements

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎓 WORKFLOW 6: Continuous Learning Setup
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Purpose: Set up self-improving organization

Steps:
  1. Initial organization (Workflow 1 or 2)

  2. Use the system regularly
     → System tracks your file movements/corrections

  3. View Learning Analytics (option 19)
     → See what preferences system learned

  4. Run Smart Auto-Organize periodically (option 8)
     → System applies learned preferences

  5. Monitor accuracy improvement (option 19)
     → Track how system gets better over time

Time: Ongoing
Result: System that learns your preferences and improves

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 TIPS FOR SUCCESS

  ✓ Always run "Scan & Index" (option 1) first
  ✓ Use dry-run mode when trying new operations
  ✓ Start with a small test folder before full organization
  ✓ Review AI suggestions before executing
  ✓ Keep backups before major reorganizations
  ✓ Use option 20 (Report) to track progress over time
  ✓ Enhanced features (16-21) work best after option 21

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

        input("\nPress Enter to return to menu...")

    def show_workflow(self, workflow_name: str):
        """Show a specific guided workflow"""
        print_header("GUIDED WORKFLOW")

        workflows = {
            "complete_organization": {
                "title": "🎯 Complete Organization (First-Time Setup)",
                "time": "30-60 minutes",
                "purpose": "Fully organize a messy folder for the first time",
                "steps": [
                    ("1", "Scan & Index Files", "Fast regex-based indexing"),
                    ("20", "Process Files Comprehensively", "Extract content, embeddings, hashes"),
                    ("15", "Find All Duplicates", "4 detection types"),
                    ("22", "Consolidate Duplicates", "Remove duplicates"),
                    ("3", "LLM Analyze Structure", "AI suggests organization"),
                    ("17", "Validate Quality", "Check organization quality"),
                    ("7", "Execute Recommendations", "Apply AI suggestions"),
                    ("19", "Generate Report", "Get comprehensive analysis")
                ]
            },
            "duplicate_cleanup": {
                "title": "🔍 Duplicate Detection & Cleanup",
                "time": "10-20 minutes",
                "purpose": "Find and remove duplicate files",
                "steps": [
                    ("1", "Scan & Index Files", "Index all files"),
                    ("20", "Process Files (hashes only)", "Calculate hashes for duplication"),
                    ("15", "Find All Duplicates", "4 types: exact/content/perceptual/semantic"),
                    ("22", "Consolidate Duplicates", "Keep best, move rest to _Duplicate_Files/")
                ]
            },
            "content_based": {
                "title": "🧩 Content-Based Organization",
                "time": "20-30 minutes",
                "purpose": "Organize by document content/meaning",
                "steps": [
                    ("1", "Scan & Index Files", "Index all files"),
                    ("20", "Process Files (extract + embed)", "Generate embeddings"),
                    ("16", "Cluster Similar Documents", "Group by semantic similarity"),
                    ("Use clusters to create folders", "Based on cluster names", ""),
                    ("24", "Move files to cluster folders", "Manual or by extension")
                ]
            },
            "quality_assessment": {
                "title": "📊 Quality Assessment & Improvement",
                "time": "15-25 minutes",
                "purpose": "Assess and improve existing organization",
                "steps": [
                    ("1", "Scan & Index Files", "Index current state"),
                    ("17", "Validate Quality", "Get 4D quality scores"),
                    ("10", "Fix Poor Filenames", "Address naming issues"),
                    ("Review recommendations", "Check quality report", ""),
                    ("17", "Re-validate", "Measure improvement")
                ]
            }
        }

        if workflow_name not in workflows:
            print("Unknown workflow")
            return

        wf = workflows[workflow_name]

        print(f"\n{wf['title']}")
        print("=" * 60)
        print(f"Purpose: {wf['purpose']}")
        print(f"Time: {wf['time']}")
        print("\nSteps:")
        print("-" * 60)

        for i, step in enumerate(wf['steps'], 1):
            if len(step) == 3:
                option, action, description = step
                if option and option.isdigit():
                    print(f"\n{i}. Option {option}: {action}")
                else:
                    print(f"\n{i}. {option}")
                if description:
                    print(f"   → {description}")
            else:
                print(f"\n{i}. {step}")

        print("\n" + "=" * 60)
        print("💡 Follow steps in order for best results")
        print("   Each step prepares data for the next")

        input("\nPress Enter to return to menu...")

    def cleanup(self):
        """Cleanup resources"""
        if self.analyzer:
            self.analyzer.cleanup()


def main():
    """Main entry point"""
    print_header("SMART FILE ORGANIZER")
    print("Index → Aggregate → LLM Analyze → Apply")
    print()

    # Get root path
    default_root = "E:/Organization_Folder/01_Court_Information"

    root_input = input(f"Enter root folder to organize [{default_root}]: ").strip()
    root_path = root_input if root_input else default_root

    if not Path(root_path).exists():
        print(f"❌ Path does not exist: {root_path}")
        return

    organizer = SmartOrganizer(root_path)

    try:
        while True:
            print("\n" + "=" * 60)
            print("SMART FILE ORGANIZER - MAIN MENU")
            print("=" * 60)

            # Core Operations
            print("\n📊 CORE OPERATIONS")
            print("-" * 60)
            print("1.  Scan & Index Files")
            print("2.  Show Statistics")
            print("3.  LLM Analyze Structure")
            print("4.  LLM Analyze Folder")
            print("5.  Get Rename Suggestions")
            print("6.  Show Pending Actions")

            # Quick Actions
            print("\n⚡ QUICK ACTIONS")
            print("-" * 60)
            print("7.  Execute All Recommendations")
            print("8.  Smart Auto-Organize (analyze + execute)")
            print("9.  Smart Cleanup (rule-based)")
            print("10. Fix Poor Filenames")

            # Guided Workflows
            print("\n📋 GUIDED WORKFLOWS")
            print("-" * 60)
            print("11. Complete Organization (first-time setup)")
            print("12. Duplicate Detection & Cleanup")
            print("13. File-Level Auto-Organize (per-file moves)")
            print("14. Quality Assessment")
            print("26. Full Pipeline (index->process->dedupe->analyze->report)")

            # Enhanced Features
            print("\n🚀 ENHANCED FEATURES")
            print("-" * 60)
            print("15. Find All Duplicates (4 detection types)")
            print("16. Cluster Similar Documents")
            print("17. Validate Quality (4D scoring)")
            print("18. View Learning Analytics")
            print("19. Generate Report")
            print("20. Process Files (comprehensive)")

            # File Operations
            print("\n🔧 FILE OPERATIONS")
            print("-" * 60)
            print("21. Find Duplicates (basic)")
            print("22. Consolidate Duplicates")
            print("23. Find Files by Pattern")
            print("24. Move by Extension")
            print("25. Create Recommended Folders")

            # System
            print("\n⚙️  SYSTEM")
            print("-" * 60)
            print("99. Clear Database")
            print("0.  Exit")
            print("=" * 60)

            choice = input("\nChoice: ").strip()

            if choice == "1":
                organizer.scan()

            elif choice == "2":
                organizer.show_statistics()

            elif choice == "3":
                organizer.analyze()

            elif choice == "4":
                stats = organizer.index.get_statistics(root_path=organizer.root_path)
                folders = [f['folder_path'] for f in stats['top_folders'][:20]]

                print("\nTop folders:")
                for i, f in enumerate(folders[:20], 1):
                    print(f"  {i}. {f or '(root)'}")

                folder_input = input("\nEnter folder path or number: ").strip()

                if folder_input.isdigit():
                    idx = int(folder_input) - 1
                    if 0 <= idx < len(folders):
                        folder = folders[idx]
                    else:
                        print("Invalid selection")
                        continue
                else:
                    folder = folder_input

                organizer.analyze_folder(folder)

            elif choice == "5":
                ext = input("Filter by extension (e.g., .pdf) or Enter for all: ").strip()
                organizer.get_rename_suggestions(extension=ext if ext else None)

            elif choice == "6":
                organizer.show_pending_actions()

            elif choice == "7":
                organizer.execute_all_actions()

            elif choice == "8":
                organizer.smart_organize()

            elif choice == "9":
                min_copies = input("Minimum copies to show (default 2): ").strip()
                organizer.find_duplicates(int(min_copies) if min_copies else 2)

            elif choice == "9":
                organizer.smart_cleanup()

            elif choice == "10":
                organizer.show_poor_filenames()

            elif choice == "11":
                organizer.show_workflow("complete_organization")

            elif choice == "12":
                organizer.show_workflow("duplicate_cleanup")

            elif choice == "13":
                organizer.generate_file_level_actions()

            elif choice == "14":
                organizer.show_workflow("quality_assessment")

            elif choice == "26":
                organizer.run_full_pipeline()

            elif choice == "15":
                organizer.find_all_duplicates_enhanced()

            elif choice == "16":
                organizer.cluster_documents_interactive()

            elif choice == "17":
                organizer.validate_quality_interactive()

            elif choice == "18":
                organizer.show_learning_analytics()

            elif choice == "19":
                organizer.generate_comprehensive_report()

            elif choice == "20":
                organizer.process_files_comprehensive_interactive()

            elif choice == "21":
                organizer.find_duplicates_simple()

            elif choice == "22":
                print("\nConsolidate duplicates - keeps newest copy, moves rest to _Duplicate_Files/")
                pattern = input("Filename pattern (* for all, or e.g., context.mdb): ").strip()
                min_copies = input("Minimum copies (default 2): ").strip()

                if pattern == '*':
                    pattern = None

                organizer.consolidate_duplicates(
                    filename_pattern=pattern,
                    min_copies=int(min_copies) if min_copies else 2
                )

            elif choice == "23":
                pattern = input("Enter pattern (use * for wildcard): ").strip()
                if pattern:
                    organizer.find_by_pattern(pattern)

            elif choice == "24":
                ext = input("Extension to move (e.g., .mdb): ").strip()
                dest = input("Destination folder: ").strip()
                if ext and dest:
                    organizer.move_by_extension(ext, dest)

            elif choice == "25":
                organizer.apply_folder_creation()

            elif choice == "99":
                organizer.clear_database()

            elif choice == "0":
                break

            else:
                print("Invalid choice")

    finally:
        organizer.cleanup()

    print("\nGoodbye!")


if __name__ == "__main__":
    main()
