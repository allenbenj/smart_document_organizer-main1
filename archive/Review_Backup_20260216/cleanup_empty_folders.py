#!/usr/bin/env python3
"""
Clean up all empty folders from bad organization.
"""

from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

def remove_empty_folders(base_path: Path):
    """Recursively remove all empty folders."""

    console.print(f"\n[bold]Scanning for empty folders in {base_path}[/bold]\n")

    removed_count = 0

    for category in ["Projects", "Resources", "Areas", "Archives"]:
        category_path = base_path / category
        if not category_path.exists():
            continue

        console.print(f"[cyan]Checking {category}...[/cyan]")

        # Walk bottom-up to remove nested empty folders
        for root, dirs, files in category_path.walk(top_down=False):
            for dirname in dirs:
                dir_path = Path(root) / dirname
                try:
                    # Check if directory is empty
                    if not any(dir_path.iterdir()):
                        dir_path.rmdir()
                        removed_count += 1
                        console.print(f"  [dim]Removed: {dir_path.relative_to(base_path)}[/dim]")
                except Exception as e:
                    # Directory not empty or other error
                    pass

    console.print(f"\n[green]✓ Removed {removed_count} empty folders[/green]")
    return removed_count


if __name__ == "__main__":
    base = Path(r"E:\Organization_Folder\02_Working_Folder")
    remove_empty_folders(base)
