#!/usr/bin/env python3
"""
Final organization: Move files from 4 folders to appropriate locations, then delete those folders.
"""

import json
import shutil
from pathlib import Path
from typing import List, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field
from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table

from openai import OpenAI

console = Console()

# Folders to DELETE after processing
FOLDERS_TO_DELETE = [
    r"E:\Organization_Folder\02_Working_Folder\Archives",
    r"E:\Organization_Folder\02_Working_Folder\Areas",
    r"E:\Organization_Folder\02_Working_Folder\Projects",
    r"E:\Organization_Folder\02_Working_Folder\Resources"
]

# Folders to EXCLUDE from being used as targets (includes folders to delete + banned folders)
EXCLUDE_FROM_TARGETS = FOLDERS_TO_DELETE + [
    r"E:\Organization_Folder\01_Correspondence"
]

BASE_ORG_FOLDER = Path(r"E:\Organization_Folder")


class FileCategorization(BaseModel):
    """File organization decision from Grok."""
    target_folder: str = Field(description="Full path to target folder (relative to E:\\Organization_Folder)")
    reasoning: str = Field(description="Detailed explanation for this categorization")
    confidence: int = Field(description="Confidence score 0-100", ge=0, le=100)
    suggested_rename: str | None = Field(description="Optional better filename", default=None)


def scan_available_folders(base_path: Path, exclude_folders: List[str]) -> List[str]:
    """Scan all folders under base_path, excluding specified folders."""
    available = []
    exclude_paths = [Path(f) for f in exclude_folders]

    for folder in base_path.rglob("*"):
        if folder.is_dir():
            # Skip if it's one of the folders to delete
            if any(folder == exc or folder in exc.parents or exc in folder.parents for exc in exclude_paths):
                continue
            # Add relative path
            rel_path = folder.relative_to(base_path)
            available.append(str(rel_path))

    return sorted(available)


def collect_files_to_process(folders: List[str]) -> List[Path]:
    """Collect all .md and .docx files from specified folders."""
    all_files = []

    for folder_str in folders:
        folder = Path(folder_str)
        if folder.exists():
            # Only get files at ROOT of this folder, not subdirectories
            md_files = list(folder.glob("*.md"))
            docx_files = list(folder.glob("*.docx"))
            # Verify files actually exist
            all_files.extend([f for f in md_files if f.exists() and f.is_file()])
            all_files.extend([f for f in docx_files if f.exists() and f.is_file()])

    return all_files


def extract_content(file_path: Path) -> str:
    """Extract content from file."""
    suffix = file_path.suffix.lower()

    try:
        if suffix == ".md":
            return file_path.read_text(encoding='utf-8', errors='ignore')
        elif suffix == ".docx":
            try:
                from docx import Document
                doc = Document(file_path)
                return "\n".join([para.text for para in doc.paragraphs])
            except:
                return f"[DOCX file: {file_path.name}]"
        else:
            return f"[{suffix.upper()} file: {file_path.name}]"
    except Exception as e:
        logger.error(f"Failed to extract content from {file_path}: {e}")
        return f"[Error reading file: {file_path.name}]"


def categorize_file(client: OpenAI, file_path: Path, content: str, available_folders: List[str]) -> FileCategorization:
    """Categorize file using Grok."""

    # Limit folder list in prompt (show first 50)
    folder_list = "\n".join([f"  - {f}" for f in available_folders[:50]])
    if len(available_folders) > 50:
        folder_list += f"\n  ... and {len(available_folders) - 50} more folders"

    system_prompt = f"""You are an expert file organization assistant.

You must choose ONE of the available folders below to place this file.
Choose the MOST APPROPRIATE folder based on the file content.

AVAILABLE FOLDERS:
{folder_list}

CRITICAL: You MUST use one of the folders listed above. Return the EXACT folder path as shown."""

    user_prompt = f"""Categorize this document into the most appropriate folder.

Filename: {file_path.name}
File type: {file_path.suffix}

CONTENT:
{content[:5000]}

Determine:
1. Which folder from the list is most appropriate
2. Your reasoning
3. Confidence level (0-100)
4. Optional: A better filename if current one is unclear"""

    try:
        response = client.beta.chat.completions.parse(
            model="grok-4-1-fast-reasoning",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format=FileCategorization,
            temperature=0.3,
        )

        return response.choices[0].message.parsed

    except Exception as e:
        logger.error(f"Grok API error for {file_path.name}: {e}")
        # Fallback to first available folder
        return FileCategorization(
            target_folder=available_folders[0] if available_folders else "02_Working_Folder",
            reasoning=f"Error: {str(e)}",
            confidence=0
        )


def move_file(source: Path, categorization: FileCategorization, base_path: Path):
    """Move file to target location."""

    target_dir = base_path / categorization.target_folder
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = categorization.suggested_rename if categorization.suggested_rename else source.name
    target_file = target_dir / filename

    # Handle duplicates
    counter = 1
    while target_file.exists():
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        target_file = target_dir / f"{stem}_{counter}{suffix}"
        counter += 1

    try:
        shutil.move(str(source), str(target_file))
        logger.info(f"Moved: {source.name} → {categorization.target_folder}")
        return True
    except Exception as e:
        logger.error(f"Failed to move {source}: {e}")
        return False


def delete_folders(folders: List[str]):
    """Delete the specified folders."""
    console.print("\n[bold red]Deleting source folders...[/bold red]")

    for folder_str in folders:
        folder = Path(folder_str)
        if folder.exists():
            try:
                shutil.rmtree(folder)
                console.print(f"  [red]✓ Deleted: {folder.name}[/red]")
            except Exception as e:
                console.print(f"  [yellow]✗ Failed to delete {folder.name}: {e}[/yellow]")


def main():
    """Main execution."""
    import os
    import sys

    # Check for file limit argument
    file_limit = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    auto_delete = "--delete" in sys.argv

    api_key = os.getenv("GROK_API_KEY", "xai-6mAVN4baeVItMqXsgTclktNjTVjO2LdI6vBEeXh2MH1wgdm9EPWVcAHNRC7R9k1Xy9SzNqueJ9o9NztY")
    client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")

    # Scan available folders
    console.print("\n[bold]Scanning available folders...[/bold]")
    available_folders = scan_available_folders(BASE_ORG_FOLDER, EXCLUDE_FROM_TARGETS)
    console.print(f"Found {len(available_folders)} available target folders\n")

    # Collect files to process
    console.print("[bold]Collecting files to process...[/bold]")
    all_files = collect_files_to_process(FOLDERS_TO_DELETE)
    console.print(f"Found {len(all_files)} total files")

    # Limit files for testing
    files = all_files[:file_limit]
    console.print(f"[cyan]Processing {len(files)} files this run[/cyan]\n")

    if not files:
        console.print("[yellow]No files to process![/yellow]")
        return

    # Track results for evaluation
    results = []
    total_moved = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console
    ) as progress:
        task = progress.add_task("Organizing files...", total=len(files))

        for file_path in files:
            # Skip if file no longer exists
            if not file_path.exists():
                logger.warning(f"File no longer exists, skipping: {file_path}")
                progress.advance(task)
                continue

            try:
                # Extract content
                content = extract_content(file_path)

                # Categorize
                categorization = categorize_file(client, file_path, content, available_folders)

                # Move
                success = move_file(file_path, categorization, BASE_ORG_FOLDER)
                if success:
                    total_moved += 1

                # Track for report
                results.append({
                    'original_name': file_path.name,
                    'new_name': categorization.suggested_rename or file_path.name,
                    'target_folder': categorization.target_folder,
                    'reasoning': categorization.reasoning,
                    'confidence': categorization.confidence,
                    'success': success
                })
            except Exception as e:
                logger.error(f"Error processing {file_path.name}: {e}")
                results.append({
                    'original_name': file_path.name,
                    'new_name': file_path.name,
                    'target_folder': 'ERROR',
                    'reasoning': f"Error: {str(e)}",
                    'confidence': 0,
                    'success': False
                })

            progress.advance(task)

    # Show detailed results
    console.print(f"\n[bold green]✓ Processed {total_moved}/{len(files)} files[/bold green]\n")

    # Create summary table
    table = Table(title="Organization Results (Last 20 files)")
    table.add_column("Original Name", style="cyan", max_width=30)
    table.add_column("New Name", style="green", max_width=30)
    table.add_column("Target Folder", style="yellow", max_width=40)
    table.add_column("Conf", justify="right", style="magenta")

    for result in results[-20:]:
        conf_color = "green" if result['confidence'] >= 80 else "yellow" if result['confidence'] >= 60 else "red"
        table.add_row(
            result['original_name'][:30],
            result['new_name'][:30] if result['new_name'] != result['original_name'] else "[dim]same[/dim]",
            result['target_folder'][:40],
            f"[{conf_color}]{result['confidence']}%[/{conf_color}]"
        )

    console.print(table)

    # Save full results to JSON
    results_file = Path("final_organize_results.json")
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    console.print(f"\n[dim]Full results saved to: {results_file}[/dim]")

    # Show confidence statistics
    avg_conf = sum(r['confidence'] for r in results) / len(results)
    low_conf = [r for r in results if r['confidence'] < 70]
    console.print(f"\n[bold]Statistics:[/bold]")
    console.print(f"  Average confidence: {avg_conf:.1f}%")
    console.print(f"  Low confidence (<70%): {len(low_conf)} files")

    console.print(f"\n[yellow]Remaining files: {len(all_files) - len(files)}[/yellow]")

    if auto_delete and len(all_files) == len(files):
        # Only delete if we processed ALL files
        delete_folders(FOLDERS_TO_DELETE)
        console.print("\n[bold green]✓✓✓ COMPLETE - Source folders deleted ✓✓✓[/bold green]\n")
    else:
        console.print(f"\n[cyan]Run with --delete flag after all files processed to delete source folders[/cyan]\n")


if __name__ == "__main__":
    main()
