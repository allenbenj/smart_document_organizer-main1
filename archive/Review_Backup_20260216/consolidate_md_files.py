#!/usr/bin/env python3
"""
Consolidate markdown files from over-organized folders into existing structure.
"""

import os
from pathlib import Path
from collections import defaultdict
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
import shutil

console = Console()

def scan_existing_folders(base_path: Path) -> dict:
    """Scan and return existing folder structure."""
    structure = {}

    for category in ["Projects", "Resources", "Areas", "Archives"]:
        cat_path = base_path / category
        if cat_path.exists():
            structure[category] = []
            for item in cat_path.iterdir():
                if item.is_dir():
                    structure[category].append(item.name)

    return structure

def scan_md_files(base_path: Path) -> list:
    """Find all markdown files in organized folders."""
    md_files = []

    for category in ["Projects", "Resources", "Areas", "Archives"]:
        cat_path = base_path / category
        if cat_path.exists():
            md_files.extend(cat_path.rglob("*.md"))

    return md_files

def consolidate_files(base_path: Path, dry_run=False):
    """Consolidate files from single-file folders into broader categories."""

    console.print(f"\n[bold]Scanning {base_path}[/bold]\n")

    # Find all markdown files
    all_files = scan_md_files(base_path)
    console.print(f"Found {len(all_files)} markdown files\n")

    # Group files by their current directory
    folder_file_count = defaultdict(list)
    for file in all_files:
        folder = file.parent
        folder_file_count[folder].append(file)

    # Find folders with only 1 file (bad organization)
    single_file_folders = {folder: files for folder, files in folder_file_count.items()
                          if len(files) == 1}

    console.print(f"[yellow]Found {len(single_file_folders)} folders with only 1 file[/yellow]\n")

    if not single_file_folders:
        console.print("[green]No cleanup needed - folder structure looks good![/green]")
        return

    # Group by category to find common broader folders
    by_category = defaultdict(list)
    for folder, files in single_file_folders.items():
        # Determine category (Projects, Resources, etc.)
        category = None
        for cat in ["Projects", "Resources", "Areas", "Archives"]:
            if (base_path / cat) in folder.parents or folder.parent == (base_path / cat):
                category = cat
                break
        if category:
            by_category[category].extend(files)

    console.print("[bold]Files to consolidate by category:[/bold]\n")
    for category, files in by_category.items():
        console.print(f"  {category}: {len(files)} files")

    if dry_run:
        console.print("\n[yellow]DRY RUN - No actual moves performed[/yellow]")
        return

    # Move files to category root and clean up empty folders
    moved_count = 0
    removed_folders = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console
    ) as progress:
        task = progress.add_task("Consolidating files...", total=len(single_file_folders))

        for folder, files in single_file_folders.items():
            for file in files:
                # Determine category
                category = None
                for cat in ["Projects", "Resources", "Areas", "Archives"]:
                    if (base_path / cat) in file.parents:
                        category = cat
                        break

                if category:
                    # Move to category root
                    target = base_path / category / file.name

                    # Handle duplicates
                    counter = 1
                    while target.exists():
                        stem = file.stem
                        suffix = file.suffix
                        target = base_path / category / f"{stem}_{counter}{suffix}"
                        counter += 1

                    try:
                        shutil.move(str(file), str(target))
                        moved_count += 1
                    except Exception as e:
                        console.print(f"[red]Error moving {file.name}: {e}[/red]")

            # Try to remove empty folder
            try:
                if folder.exists() and not any(folder.iterdir()):
                    folder.rmdir()
                    removed_folders += 1
            except:
                pass

            progress.advance(task)

    console.print(f"\n[green]✓ Moved {moved_count} files[/green]")
    console.print(f"[green]✓ Removed {removed_folders} empty folders[/green]")


if __name__ == "__main__":
    base = Path(r"E:\Organization_Folder\02_Working_Folder")
    consolidate_files(base, dry_run=False)
