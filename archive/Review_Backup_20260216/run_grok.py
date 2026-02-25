#!/usr/bin/env python3
"""
Quick runner for Grok organizer.
Processes full documents with 2M context window.
"""

from grok_organizer import GrokOrganizer
from rich.console import Console

if __name__ == "__main__":
    console = Console()

    console.print("[bold green]🤖 Grok File Organizer[/bold green]")
    console.print("Using 2M context window for full document analysis\n")

    # Grok API configuration
    GROK_API_KEY = 

    organizer = GrokOrganizer(
        api_key=GROK_API_KEY,
        model="grok-4-1-fast-reasoning",
        dry_run=False,  # Actually move files
        console=console
    )

    try:
        organizer.organize(
            input_path=r"E:\Organization_Folder\02_Working_Folder\18_Review\02_docx",
            output_path=r"E:\Organization_Folder\02_Working_Folder",
            extensions=[".docx", ".pdf", ".txt"]  # File types to process
        )

        console.print("\n[bold cyan]Next steps:[/bold cyan]")
        console.print("1. Review the organization plan above")
        console.print("2. If satisfied, set dry_run=False in the script")
        console.print("3. Run again to actually organize the files")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()

