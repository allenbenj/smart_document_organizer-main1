#!/usr/bin/env python3
"""
Grok-Powered File Organizer

Leverages Grok's 2M context window to process FULL documents for intelligent organization.
Single-stage approach using Grok-4-1-fast-reasoning for accurate categorization.
"""

import json
from pathlib import Path
from typing import List, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field
from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table

from openai import OpenAI


# Pydantic schema for Grok's structured output
class CategoryType(str, Enum):
    """PARA methodology categories."""
    PROJECTS = "Projects"
    AREAS = "Areas"
    RESOURCES = "Resources"
    ARCHIVES = "Archives"


class FileCategorization(BaseModel):
    """File organization decision from Grok."""
    category: CategoryType = Field(description="Main PARA category")
    subcategory: str = Field(description="Specific folder name within category")
    reasoning: str = Field(description="Detailed explanation for this categorization")
    confidence: int = Field(description="Confidence score 0-100", ge=0, le=100)
    suggested_rename: str | None = Field(description="Optional better filename", default=None)


class GrokOrganizer:
    """
    File organizer using Grok's massive context window.

    Processes entire documents (up to 2M tokens) for accurate categorization.
    Uses structured outputs for reliable JSON responses.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "grok-4-1-fast-reasoning",
        dry_run: bool = True,
        console: Console | None = None
    ):
        """
        Initialize Grok organizer.

        Args:
            api_key: Grok API key from x.ai
            model: Grok model to use
            dry_run: If True, don't actually move files
            console: Rich console for output
        """
        self.console = console or Console()
        self.dry_run = dry_run
        self.model = model

        # Initialize OpenAI client pointing to Grok
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1"
        )

        self.results: List[Dict[str, Any]] = []
        self.existing_folders: Dict[str, List[str]] = {}

    def extract_content(self, file_path: Path) -> str:
        """
        Extract full content from document.

        Args:
            file_path: Path to file

        Returns:
            Full text content (Grok can handle 2M tokens!)
        """
        suffix = file_path.suffix.lower()

        try:
            if suffix == ".txt":
                return file_path.read_text(encoding='utf-8', errors='ignore')

            elif suffix == ".docx":
                try:
                    from docx import Document
                    doc = Document(file_path)
                    return "\n".join([para.text for para in doc.paragraphs])
                except ImportError:
                    logger.warning("python-docx not installed, using filename only")
                    return f"[DOCX file: {file_path.name}]"

            elif suffix == ".pdf":
                try:
                    import PyPDF2
                    with open(file_path, 'rb') as f:
                        reader = PyPDF2.PdfReader(f)
                        text = []
                        for page in reader.pages:
                            text.append(page.extract_text())
                        return "\n".join(text)
                except ImportError:
                    logger.warning("PyPDF2 not installed, using filename only")
                    return f"[PDF file: {file_path.name}]"

            else:
                return f"[{suffix.upper()} file: {file_path.name}]"

        except Exception as e:
            logger.error(f"Failed to extract content from {file_path}: {e}")
            return f"[Error reading file: {file_path.name}]"

    def _scan_existing_folders(self, output_path: Path) -> Dict[str, List[str]]:
        """
        Scan existing folder structure in output directory.

        Args:
            output_path: Target organization directory

        Returns:
            Dict mapping category to list of existing subcategories
        """
        folders = {cat.value: [] for cat in CategoryType}

        for category in CategoryType:
            category_path = output_path / category.value
            if category_path.exists() and category_path.is_dir():
                # Get all subdirectories
                subdirs = [d.name for d in category_path.iterdir() if d.is_dir()]
                folders[category.value] = subdirs

        return folders

    def categorize_file(self, file_path: Path, content: str) -> FileCategorization:
        """
        Categorize a single file using Grok with full content.

        Args:
            file_path: Path to file
            content: Full document content

        Returns:
            Categorization decision from Grok
        """
        # Build existing folders info for prompt
        existing_info = ""
        if self.existing_folders:
            existing_info = "\n\nEXISTING FOLDERS (PREFER THESE):\n"
            for category, folders in self.existing_folders.items():
                if folders:
                    existing_info += f"\n{category}:\n"
                    for folder in folders[:20]:  # Limit to first 20
                        existing_info += f"  - {folder}\n"

        system_prompt = f"""You are an expert file organization assistant using the PARA methodology:

- Projects: Active work with deadlines and deliverables
- Areas: Ongoing responsibilities (Health, Finances, Family, etc.)
- Resources: Reference materials and topics of interest
- Archives: Completed or inactive items

CRITICAL RULES:
1. You MUST use one of the existing folders listed below - DO NOT create new subcategories
2. Choose the MOST APPROPRIATE existing folder from the list
3. If no exact match exists, choose the closest/most general existing folder
{existing_info}

Analyze the FULL document content and determine the best organization."""

        user_prompt = f"""Categorize this document for a well-organized file system.

Filename: {file_path.name}
File type: {file_path.suffix}

FULL CONTENT:
{content}

Based on the complete content above, determine:
1. Which PARA category fits best
2. A specific, descriptive subcategory (folder name)
3. Your reasoning
4. Confidence level (0-100)
5. Optional: A better filename if current one is unclear"""

        try:
            response = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=FileCategorization,
                temperature=0.3,
            )

            categorization = response.choices[0].message.parsed
            return categorization

        except Exception as e:
            logger.error(f"Grok API error for {file_path.name}: {e}")
            # Fallback
            return FileCategorization(
                category=CategoryType.RESOURCES,
                subcategory="Uncategorized",
                reasoning=f"Error: {str(e)}",
                confidence=0
            )

    def organize(
        self,
        input_path: str | Path,
        output_path: str | Path,
        extensions: List[str] | None = None,
        max_files: int | None = None
    ):
        """
        Organize files from input to output directory.

        Args:
            input_path: Directory with files to organize
            output_path: Target organization directory
            extensions: File extensions to process (default: .docx, .pdf, .txt)
            max_files: Maximum number of files to process (default: all)
        """
        input_path = Path(input_path)
        output_path = Path(output_path)

        if extensions is None:
            extensions = [".docx", ".pdf", ".txt"]

        # Collect files
        self.console.print(f"\n[bold]Scanning:[/bold] {input_path}")
        files = []
        for ext in extensions:
            files.extend(input_path.rglob(f"*{ext}"))

        if not files:
            self.console.print(f"[yellow]No files found with extensions {extensions}[/yellow]")
            return

        # Limit files if max_files specified
        if max_files:
            files = files[:max_files]

        self.console.print(f"Found {len(files)} files to process\n")

        # Scan existing folder structure
        self.existing_folders = self._scan_existing_folders(output_path)
        folder_count = sum(len(folders) for folders in self.existing_folders.values())
        if folder_count > 0:
            self.console.print(f"[dim]Found {folder_count} existing folders to reuse[/dim]\n")

        # Process each file with Grok
        self.console.print("[bold cyan]Processing with Grok (2M context window)[/bold cyan]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console
        ) as progress:
            task = progress.add_task("Categorizing files...", total=len(files))

            for file_path in files:
                # Extract FULL content
                content = self.extract_content(file_path)

                # Get categorization from Grok
                categorization = self.categorize_file(file_path, content)

                self.results.append({
                    "file": file_path,
                    "categorization": categorization
                })

                # Move file immediately
                if not self.dry_run:
                    self._move_single_file(file_path, categorization, output_path)

                progress.advance(task)

        # Display results
        self._display_results()

        # Clean up empty folders
        if not self.dry_run:
            self._cleanup_empty_folders(output_path)
            self.console.print(f"\n[green]✓ All files organized successfully[/green]")
        else:
            self.console.print("\n[yellow]DRY RUN: No files moved[/yellow]")
            self.console.print(f"[dim]Set dry_run=False to actually organize files[/dim]")

    def _display_results(self):
        """Display categorization results in a table."""
        table = Table(title="\n📂 Grok Organization Plan")
        table.add_column("File", style="cyan", max_width=40)
        table.add_column("Category", style="green")
        table.add_column("Subcategory", style="blue")
        table.add_column("Confidence", style="yellow", justify="right")

        # Sort by category then subcategory
        sorted_results = sorted(
            self.results,
            key=lambda x: (x["categorization"].category.value, x["categorization"].subcategory)
        )

        for result in sorted_results[:30]:  # Show first 30
            cat = result["categorization"]
            file_path = result["file"]

            confidence_display = f"{cat.confidence}%"
            if cat.confidence >= 90:
                confidence_display = f"[green]{confidence_display}[/green]"
            elif cat.confidence >= 70:
                confidence_display = f"[yellow]{confidence_display}[/yellow]"
            else:
                confidence_display = f"[red]{confidence_display}[/red]"

            table.add_row(
                file_path.name,
                cat.category.value,
                cat.subcategory,
                confidence_display
            )

        self.console.print(table)

        # Summary
        avg_confidence = sum(r["categorization"].confidence for r in self.results) / len(self.results)
        self.console.print(f"\n[bold]Summary:[/bold]")
        self.console.print(f"  Total files: {len(self.results)}")
        self.console.print(f"  Average confidence: {avg_confidence:.1f}%")

        # Category breakdown
        categories = {}
        for result in self.results:
            cat = result["categorization"].category.value
            categories[cat] = categories.get(cat, 0) + 1

        self.console.print(f"\n[bold]Category breakdown:[/bold]")
        for cat, count in sorted(categories.items()):
            self.console.print(f"  {cat}: {count} files")

    def _move_single_file(self, source: Path, categorization: FileCategorization, output_path: Path):
        """Move a single file immediately after categorization."""
        import shutil

        # Build target path
        subcategory_clean = categorization.subcategory.replace('\\', '-').replace('/', '-')
        target_dir = output_path / categorization.category.value / subcategory_clean
        target_dir.mkdir(parents=True, exist_ok=True)

        # Use suggested rename if available, otherwise keep original name
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
            shutil.move(source, target_file)
            logger.info(f"Moved: {source.name} → {categorization.category.value}/{categorization.subcategory}")
        except Exception as e:
            logger.error(f"Failed to move {source}: {e}")

    def _cleanup_empty_folders(self, output_path: Path):
        """Remove empty folders after reorganization."""
        self.console.print("\n[dim]Cleaning up empty folders...[/dim]")

        removed_count = 0
        for category in CategoryType:
            category_path = output_path / category.value
            if category_path.exists() and category_path.is_dir():
                # Walk from bottom up to remove empty subdirectories
                for dirpath, dirnames, filenames in category_path.walk(top_down=False):
                    for dirname in dirnames:
                        dir_to_check = Path(dirpath) / dirname
                        try:
                            if not any(dir_to_check.iterdir()):
                                dir_to_check.rmdir()
                                removed_count += 1
                                logger.debug(f"Removed empty folder: {dir_to_check}")
                        except Exception as e:
                            logger.debug(f"Could not remove {dir_to_check}: {e}")

        if removed_count > 0:
            self.console.print(f"[dim]Removed {removed_count} empty folders[/dim]")


def main():
    """Example usage."""
    import os

    console = Console()

    # Get API key from environment or use provided one
    api_key = os.getenv("GROK_API_KEY", "xai-6mAVN4baeVItMqXsgTclktNjTVjO2LdI6vBEeXh2MH1wgdm9EPWVcAHNRC7R9k1Xy9SzNqueJ9o9NztY")

    organizer = GrokOrganizer(
        api_key=api_key,
        model="grok-4-1-fast-reasoning",
        dry_run=False,  # Actually move files
        console=console
    )

    # Organize documents - scan already organized folders and consolidate
    organizer.organize(
        input_path=r"E:\Organization_Folder\02_Working_Folder\Projects",
        output_path=r"E:\Organization_Folder\02_Working_Folder",
        extensions=[".md"],
        max_files=100  # Process 100 files at a time
    )


if __name__ == "__main__":
    main()
