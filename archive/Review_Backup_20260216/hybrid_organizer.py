#!/usr/bin/env python3
"""
Hybrid Organizer - Two-Stage Processing

Stage 1: Local model (phi4-mini via Ollama) processes files and generates initial suggestions
Stage 2: Grok reviews batches and approves/refines the suggestions

This approach minimizes API costs while maintaining quality.
Uses Grok's structured outputs for reliable JSON parsing.
"""

import json
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum

from pydantic import BaseModel, Field
from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from file_organizer.core.organizer import FileOrganizer
from file_organizer.models import TextModel, OpenAIModel
from file_organizer.models.base import ModelConfig, ModelType
from file_organizer.services import ProcessedFile


# Pydantic schemas for structured outputs
class CategoryType(str, Enum):
    """PARA categories."""
    PROJECTS = "Projects"
    AREAS = "Areas"
    RESOURCES = "Resources"
    ARCHIVES = "Archives"


class FileSuggestion(BaseModel):
    """Single file organization suggestion."""
    category: CategoryType = Field(description="Main PARA category")
    subcategory: str = Field(description="Specific folder name within category")
    reasoning: str = Field(description="Brief explanation for this categorization")
    confidence: int = Field(description="Confidence score 0-100", ge=0, le=100)


class ReviewDecision(BaseModel):
    """Review decision for a single file."""
    index: int = Field(description="Index in the batch")
    approved: bool = Field(description="Whether to approve the local suggestion")
    final_category: CategoryType = Field(description="Final category to use")
    final_subcategory: str = Field(description="Final subcategory to use")
    changes: List[str] = Field(description="List of changes made (empty if approved)", default_factory=list)


class BatchReview(BaseModel):
    """Batch review response."""
    reviews: List[ReviewDecision] = Field(description="Reviews for each file in batch")


@dataclass
class StagedSuggestion:
    """A file organization suggestion with local and reviewed versions."""
    file_path: str
    local_suggestion: Dict[str, Any]  # From phi4-mini
    reviewed_suggestion: Dict[str, Any] | None = None  # From DeepSeek
    approved: bool = False
    changes_made: List[str] | None = None


class HybridOrganizer:
    """
    Two-stage organizer using local model for generation and cloud for review.

    Workflow:
    1. Local model processes files in chunks (fast, free)
    2. DeepSeek reviews batches of suggestions (slower, paid, but fewer calls)
    3. Final suggestions are used for organization
    """

    def __init__(
        self,
        local_model_host: str = "http://localhost:11434",
        local_model_name: str = "phi4-mini:latest",
        grok_api_key: str | None = None,
        batch_size: int = 5,
        dry_run: bool = True,
        console: Console | None = None
    ):
        """
        Initialize hybrid organizer.

        Args:
            local_model_host: Ollama server URL (WSL or local)
            local_model_name: Local model to use for generation
            grok_api_key: Grok API key from x.ai
            batch_size: Number of suggestions to review per Grok call
            dry_run: If True, don't actually move files
            console: Rich console for output
        """
        self.console = console or Console()
        self.batch_size = batch_size
        self.dry_run = dry_run

        # Stage 1: Local model configuration
        self.local_config = ModelConfig(
            name=local_model_name,
            model_type=ModelType.TEXT,
            framework="ollama",
            temperature=0.3,  # Lower for more deterministic categorization
            max_tokens=2000,
            extra_params={"host": local_model_host}
        )

        # Stage 2: Grok configuration with structured outputs
        self.review_config = ModelConfig(
            name="grok-4-1-fast-reasoning",
            model_type=ModelType.TEXT,
            framework="openai",
            temperature=0.5,
            max_tokens=4000,
            extra_params={
                "url": "https://api.x.ai/v1",
                "api_key": grok_api_key
            }

    def initialize(self):
        """Initialize both models."""
        self.console.print("[bold blue]Initializing hybrid organizer...[/bold blue]")

        # Initialize local model
        self.console.print(f"  • Stage 1: {self.local_config.name} (local processing)")
        self.local_model = TextModel(self.local_config)
        self.local_model.initialize()

        # Initialize Grok

        Args:
            file_path: Path to the file
            content: File content (first chunk)

        Returns:
            Initial suggestion dictionary
        """
        prompt = f"""Analyze this document and suggest its organization:

File: {file_path.name}
Content preview (first 2000 chars):
{content[:2000]}

Provide a JSON response with:
1. category: Main category (Projects/Areas/Resources/Archives)
2. subcategory: Specific folder name
3. reasoning: Brief explanation
4. confidence: 0-100 score

Example: {{"category": "Projects", "subcategory": "Legal Cases", "reasoning": "Contract document", "confidence": 85}}

Response (JSON only):"""

        response = self.local_model.generate(prompt)

        try:
            # Extract JSON from response
            response = response.strip()
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()

            suggestion = json.loads(response)
            return suggestion
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse local model response: {e}")
            return {
                "category": "Resources",
                "subcategory": "Uncategorized",
                "reasoning": "Failed to parse model response",
                "confidence": 0
            }

    def review_batch_with_deepseek(self, batch: List[StagedSuggestion]) -> List[StagedSuggestion]:
        """
        Stage 2: Send batch of suggestions to DeepSeek for review.

        Args:
            batch: List of suggestions from local model

        Returns:
            Updated suggestions with DeepSeek's review
        """
        # Prepare batch summary for review
        batch_summary = []
        for idx, sugg in enumerate(batch):
            batch_summary.append({
                "index": idx,
                "file": sugg.file_path,
                "local_suggestion": sugg.local_suggestion
            })

        prompt = f"""Review these file organization suggestions from a local AI model.
For each suggestion, either APPROVE it or IMPROVE it with better categorization.

Batch of {len(batch)} files:
{json.dumps(batch_summary, indent=2)}

For each file, provide:
1. approved: true/false
2. final_category: Category to use
3. final_subcategory: Subcategory to use
4. changes: List of changes made (empty if approved)

Respond with JSON array matching the input order:
[
  {{"index": 0, "approved": true, "final_category": "Projects", "final_subcategory": "Legal Cases", "changes": []}},
  ...
]

Response (JSON array only):"""

        response = self.review_model.generate(prompt)

        try:
            # Extract JSON from response
            response = response.strip()
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()

            reviews = json.loads(response)

            # Apply reviews to batch
            for review in reviews:
                idx = review["index"]
                if idx < len(batch):
                    batch[idx].approved = review.get("approved", False)
                    batch[idx].reviewed_suggestion = {
                        "category": review.get("final_category"),
                        "subcategory": review.get("final_subcategory"),
                        "reasoning": f"Reviewed by DeepSeek",
                        "confidence": 95 if review.get("approved") else 80
                    }
                    batch[idx].changes_made = review.get("changes", [])

            return batch

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse DeepSeek review: {e}")
            # Fallback: approve all local suggestions
            for sugg in batch:
                sugg.approved = True
                sugg.reviewed_suggestion = sugg.local_suggestion
            return batch

    def organize(
        self,
        input_path: str | Path,
        output_path: str | Path
    ):
        """
        Main organization workflow with two-stage processing.

        Args:
            input_path: Directory with files to organize
            output_path: Target organization directory
        """
        input_path = Path(input_path)
        output_path = Path(output_path)

        if not self.local_model or not self.review_model:
            self.initialize()

        # Collect files
        self.console.print(f"\n[bold]Scanning:[/bold] {input_path}")
        files = list(input_path.rglob("*.docx")) + list(input_path.rglob("*.pdf"))

        if not files:
            self.console.print("[yellow]No files found[/yellow]")
            return

        self.console.print(f"Found {len(files)} files\n")

        # Stage 1: Process all files with local model
        self.console.print("[bold cyan]Stage 1: Local processing[/bold cyan]")
        staged_suggestions: List[StagedSuggestion] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console
        ) as progress:
            task = progress.add_task("Processing with local model...", total=len(files))

            for file_path in files:
                try:
                    # Read content (simplified - just first part)
                    content = ""
                    if file_path.suffix == ".txt":
                        content = file_path.read_text(errors='ignore')[:2000]
                    else:
                        content = f"[{file_path.suffix.upper()} file: {file_path.name}]"

                    local_suggestion = self.process_file_with_local(file_path, content)
                    staged_suggestions.append(
                        StagedSuggestion(
                            file_path=str(file_path),
                            local_suggestion=local_suggestion
                        )
                    )
                except Exception as e:
                    logger.error(f"Failed to process {file_path}: {e}")

                progress.advance(task)

        # Stage 2: Review in batches with DeepSeek
        self.console.print(f"\n[bold cyan]Stage 2: DeepSeek review (batches of {self.batch_size})[/bold cyan]")

        reviewed_suggestions = []
        batches = [staged_suggestions[i:i+self.batch_size] for i in range(0, len(staged_suggestions), self.batch_size)]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console
        ) as progress:
            task = progress.add_task("Reviewing with DeepSeek...", total=len(batches))

            for batch in batches:
                reviewed_batch = self.review_batch_with_deepseek(batch)
                reviewed_suggestions.extend(reviewed_batch)
                progress.advance(task)

        # Display results
        self._display_results(reviewed_suggestions, output_path)

        # Execute organization (if not dry run)
        if not self.dry_run:
            self._execute_organization(reviewed_suggestions, output_path)
        else:
            self.console.print("\n[yellow]DRY RUN: No files moved[/yellow]")

    def _display_results(self, suggestions: List[StagedSuggestion], output_path: Path):
        """Display review results."""
        from rich.table import Table

        table = Table(title="\nOrganization Plan")
        table.add_column("File", style="cyan")
        table.add_column("Category", style="green")
        table.add_column("Subcategory", style="blue")
        table.add_column("Status", style="yellow")

        approved_count = sum(1 for s in suggestions if s.approved)

        for sugg in suggestions[:20]:  # Show first 20
            final = sugg.reviewed_suggestion or sugg.local_suggestion
            status = "✓ Approved" if sugg.approved else "✎ Modified"
            if sugg.changes_made:
                status += f" ({len(sugg.changes_made)} changes)"

            table.add_row(
                Path(sugg.file_path).name[:40],
                final.get("category", "Unknown"),
                final.get("subcategory", "Unknown"),
                status
            )

        self.console.print(table)
        self.console.print(f"\n[green]Approved: {approved_count}/{len(suggestions)}[/green]")
        self.console.print(f"[yellow]Modified: {len(suggestions) - approved_count}[/yellow]")

    def _execute_organization(self, suggestions: List[StagedSuggestion], output_path: Path):
        """Actually move files based on reviewed suggestions."""
        import shutil

        self.console.print("\n[bold]Moving files...[/bold]")

        for sugg in suggestions:
            final = sugg.reviewed_suggestion or sugg.local_suggestion
            source = Path(sugg.file_path)

            # Build target path
            target_dir = output_path / final["category"] / final["subcategory"]
            target_dir.mkdir(parents=True, exist_ok=True)
            target_file = target_dir / source.name

            try:
                shutil.copy2(source, target_file)
                logger.info(f"Moved: {source.name} → {target_dir.relative_to(output_path)}")
            except Exception as e:
                logger.error(f"Failed to move {source}: {e}")


def main():
    """Example usage."""
    console = Console()

    organizer = HybridOrganizer(
        local_model_host="http://localhost:11434",  # Use WSL IP if needed
        local_model_name="phi4-mini:latest",
        batch_size=5,
        dry_run=True,
        console=console
    )

    # Organize documents
    organizer.organize(
        input_path="E:/Organization_Folder/02_Working_Folder/18_Review/02_docx",
        output_path="E:/Organization_Folder/02_Working_Folder"
    )


if __name__ == "__main__":
    main()
