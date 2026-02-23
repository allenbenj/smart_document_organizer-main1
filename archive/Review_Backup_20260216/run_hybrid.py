#!/usr/bin/env python3
"""
Quick runner for the hybrid organizer.
Processes documents using local phi4-mini + DeepSeek review.
"""

from hybrid_organizer import HybridOrganizer
from rich.console import Console

if __name__ == "__main__":
    console = Console()

    console.print("[bold green]Hybrid File Organizer[/bold green]")
    console.print("Stage 1: phi4-mini (local/free) - generates suggestions")
    console.print("Stage 2: DeepSeek (cloud/paid) - reviews & improves\n")

    # Configure for your setup
    # If Ollama is on WSL, use the WSL IP address
    # To get WSL IP: wsl hostname -I
    WSL_IP = "172.26.233.62"  # Update this if your WSL IP changes

    organizer = HybridOrganizer(
        local_model_host=f"http://{WSL_IP}:11434",  # Ollama on WSL
        local_model_name="phi4-mini:latest",
        batch_size=5,  # Review 5 files at a time with DeepSeek
        dry_run=True,  # Set to False to actually move files
        console=console
    )

    try:
        organizer.organize(
            input_path=r"E:\Organization_Folder\02_Working_Folder\18_Review\02_docx",
            output_path=r"E:\Organization_Folder\02_Working_Folder"
        )
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
