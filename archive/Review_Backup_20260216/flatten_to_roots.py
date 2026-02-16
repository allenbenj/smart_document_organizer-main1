#!/usr/bin/env python3
"""
Move all markdown files from subdirectories to category roots.
"""

from pathlib import Path
import shutil
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

console = Console()

def flatten_category(category_path: Path, dry_run=False):
    """Move all .md and .docx files from subdirectories to category root."""

    moved = 0

    # Find all .md and .docx files in subdirectories (not in root)
    all_files = list(category_path.rglob("*.md")) + list(category_path.rglob("*.docx"))
    files_in_subdirs = [f for f in all_files if f.parent != category_path]
    if not files_in_subdirs:
        return 0

    console.print(f"\n[cyan]{category_path.name}:[/cyan] Found {len(files_in_subdirs)} files in subdirectories")

    if dry_run:
        console.print("  [yellow]DRY RUN - would move these files[/yellow]")
        return len(files_in_subdirs)

    for file in files_in_subdirs:
        target = category_path / file.name

        # Handle duplicates
        counter = 1
        while target.exists():
            stem = file.stem
            suffix = file.suffix
            target = category_path / f"{stem}_{counter}{suffix}"
            counter += 1

        try:
            shutil.move(str(file), str(target))
            moved += 1
        except Exception as e:
            console.print(f"  [red]Error moving {file.name}: {e}[/red]")

    return moved


def flatten_all(base_path: Path, dry_run=False):
    """Flatten all categories."""

    console.print(f"\n[bold]Flattening markdown files to category roots[/bold]")
    console.print(f"Base: {base_path}\n")

    total = 0

    for category in ["Projects", "Areas", "Archives"]:
        category_path = base_path / category
        if category_path.exists():
            count = flatten_category(category_path, dry_run)
            total += count

    console.print(f"\n[green]✓ Moved {total} files to category roots[/green]")
    console.print("[dim]You can now delete the empty subdirectories[/dim]")


if __name__ == "__main__":
    base = Path(r"E:\Organization_Folder\02_Working_Folder")
    flatten_all(base, dry_run=False)
