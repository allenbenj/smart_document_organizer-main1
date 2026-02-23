#!/usr/bin/env python3
"""
File Organizer GUI - Textual-based interface for master organization

Provides a user-friendly interface to configure and run the file organization process.
"""

import sys
import asyncio
import logging
from pathlib import Path
from typing import Optional

# Add current directory to path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Import organization components
import organizer_config
import organizer.processor

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Button, Input, Label, TextArea, RichLog, ProgressBar,
    Header, Footer, Static, DirectoryTree
)
from textual import events
from textual.binding import Binding
from textual.message import Message

# Configure logging to file only (not console for GUI)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('organization_gui.log')
    ]
)
logger = logging.getLogger(__name__)


class DirectorySelector(Container):
    """Widget for selecting directories with browse functionality"""

    def __init__(self, label: str, initial_path: str = "", **kwargs):
        super().__init__(**kwargs)
        self.label = label
        self.initial_path = initial_path

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"[bold]{self.label}[/bold]")
            with Horizontal():
                yield Input(placeholder="Enter path or browse...", value=self.initial_path, id=f"{self.label.lower().replace(' ', '_')}_input")
                yield Button("Browse", id=f"{self.label.lower().replace(' ', '_')}_browse", variant="primary")

    def get_path(self) -> str:
        input_widget = self.query_one(f"#{self.label.lower().replace(' ', '_')}_input", Input)
        return input_widget.value


class OrganizationGUI(App):
    """Main GUI application for file organization"""

    CSS = """
    Screen {
        background: $surface;
    }

    Container {
        padding: 1;
        margin: 1;
    }

    #main_container {
        width: 100%;
        height: 100%;
    }

    #header {
        background: $primary;
        color: $text;
        padding: 1;
        text-align: center;
    }

    #directory_selectors {
        background: $panel;
        border: solid $primary;
        padding: 1;
        margin: 1 0;
    }

    #config_section {
        background: $panel;
        border: solid $secondary;
        padding: 1;
        margin: 1 0;
    }

    #progress_section {
        background: $panel;
        border: solid $accent;
        padding: 1;
        margin: 1 0;
        height: 20;
    }

    #log_section {
        background: $panel;
        border: solid $border;
        padding: 1;
        margin: 1 0;
        height: 30;
    }

    Button {
        margin: 0 1;
    }

    ProgressBar {
        margin: 1 0;
    }

    TextArea {
        height: 100%;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("f1", "show_help", "Help"),
    ]

    def __init__(self):
        super().__init__()
        self.source_path = str(Path(__file__).parent / "test_files")
        self.output_path = str(Path(__file__).parent / "organized")
        self._is_running = False
        self.processor = None

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="main_container"):
            # Title
            yield Static("🗂️ File Organizer - AI-Powered Organization", id="header")

            # Directory Selection
            with Container(id="directory_selectors"):
                yield DirectorySelector("Source Directory", self.source_path)
                yield DirectorySelector("Output Directory", self.output_path)

            # Configuration
            with Container(id="config_section"):
                yield Label("[bold]Configuration[/bold]")
                with Horizontal():
                    yield Button("Load Config", id="load_config", variant="default")
                    yield Button("Save Config", id="save_config", variant="default")
                    yield Button("Reset", id="reset_config", variant="warning")

            # Control Buttons
            with Horizontal():
                yield Button("🔍 Preview", id="preview_btn", variant="default")
                yield Button("▶️ Run Organization", id="run_btn", variant="success")
                yield Button("⏹️ Stop", id="stop_btn", variant="error", disabled=True)

            # Progress Section
            with Container(id="progress_section"):
                yield Label("[bold]Progress[/bold]")
                yield ProgressBar(id="progress_bar", total=100)
                yield Static("Ready to organize files...", id="status_text")

            # Log Section
            with Container(id="log_section"):
                yield Label("[bold]Activity Log[/bold]")
                yield RichLog(id="log_textarea")

        yield Footer()

    async def on_mount(self) -> None:
        """Initialize the application"""
        self.log_message("File Organizer GUI initialized")
        self.log_message(f"Source: {self.source_path}")
        self.log_message(f"Output: {self.output_path}")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        button_id = event.button.id

        if button_id == "source_directory_browse":
            await self.browse_directory("source")
        elif button_id == "output_directory_browse":
            await self.browse_directory("output")
        elif button_id == "load_config":
            await self.load_config()
        elif button_id == "save_config":
            await self.save_config()
        elif button_id == "reset_config":
            await self.reset_config()
        elif button_id == "preview_btn":
            await self.preview_organization()
        elif button_id == "run_btn":
            await self.run_organization()
        elif button_id == "stop_btn":
            await self.stop_organization()

    async def browse_directory(self, dir_type: str) -> None:
        """Open directory browser"""
        # For now, just show a message. In a full implementation,
        # this would open a directory picker dialog
        self.log_message(f"Directory browsing for {dir_type} not implemented in this demo")
        self.log_message("Please manually enter the path in the input field")

    async def load_config(self) -> None:
        """Load configuration from file"""
        try:
            # This would load from a config file
            self.log_message("Configuration loading not implemented in this demo")
        except Exception as e:
            self.log_message(f"Error loading config: {e}")

    async def save_config(self) -> None:
        """Save current configuration"""
        try:
            config = {
                "source_path": self.source_path,
                "output_path": self.output_path
            }
            config_path = Path("gui_config.json")
            import json
            config_path.write_text(json.dumps(config, indent=2))
            self.log_message(f"Configuration saved to {config_path}")
        except Exception as e:
            self.log_message(f"Error saving config: {e}")

    async def reset_config(self) -> None:
        """Reset to default configuration"""
        self.source_path = str(Path(__file__).parent / "test_files")
        self.output_path = str(Path(__file__).parent / "organized")

        # Update input fields
        source_input = self.query_one("#source_directory_input", Input)
        output_input = self.query_one("#output_directory_input", Input)
        source_input.value = self.source_path
        output_input.value = self.output_path

        self.log_message("Configuration reset to defaults")

    async def preview_organization(self) -> None:
        """Preview what the organization would do"""
        try:
            import subprocess
            import asyncio

            self.update_status("Generating preview...")

            # Get current paths from inputs
            source_input = self.query_one("#source_directory_input", Input)
            output_input = self.query_one("#output_directory_input", Input)
            source_path = source_input.value or self.source_path
            output_path = output_input.value or self.output_path

            # Check if source exists
            if not Path(source_path).exists():
                self.log_message(f"❌ Source directory does not exist: {source_path}")
                return

            # Run with dry-run flag
            cmd = [
                sys.executable,
                str(Path(__file__).parent / "master_organization_example.py"),
                "--source", source_path,
                "--output", output_path,
                "--dry-run"
            ]

            self.log_message(f"Running preview: {' '.join(cmd)}")

            # Run in subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(Path(__file__).parent)
            )

            # Read output
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                line_text = line.decode().strip()
                if line_text:
                    self.log_message(line_text)

            await process.wait()

            if process.returncode == 0:
                self.log_message("✅ Preview completed successfully!")
                self.update_status("Preview complete")
            else:
                self.log_message(f"❌ Preview failed with code {process.returncode}")
                self.update_status("Preview failed")

        except Exception as e:
            self.log_message(f"❌ Preview error: {e}")
            self.update_status("Preview failed")

    async def run_organization(self) -> None:
        """Run the organization process"""
        if self._is_running:
            return

        try:
            self._is_running = True
            self.update_status("Starting organization...")

            # Update button states
            run_btn = self.query_one("#run_btn", Button)
            stop_btn = self.query_one("#stop_btn", Button)
            run_btn.disabled = True
            stop_btn.disabled = False

            # Get current paths
            source_input = self.query_one("#source_directory_input", Input)
            output_input = self.query_one("#output_directory_input", Input)
            source_path = source_input.value or self.source_path
            output_path = output_input.value or self.output_path

            self.log_message("🚀 Starting file organization...")
            self.log_message(f"📂 Source: {source_path}")
            self.log_message(f"📂 Output: {output_path}")

            # Create configuration
            config = organizer_config.OrganizerConfig(
                source_folder=Path(source_path),
                output_folder=Path(output_path),
                use_llm=True,
                dry_run=False,
                llm_confidence_threshold=0.8,
                enable_deduplication=True,
                enable_renaming=True,
                enable_indexing=True,
                resume_from_last_run=True
            )

            # Initialize processor
            self.processor = organizer.processor.OrganizationProcessor(config)

            # Update progress
            progress_bar = self.query_one("#progress_bar", ProgressBar)
            progress_bar.update(progress=10)

            # Run organization (in a separate task to keep UI responsive)
            await self.run_organization_async()

        except Exception as e:
            self.log_message(f"❌ Organization failed: {e}")
            self.update_status("Organization failed")
            self.reset_buttons()

    async def run_organization_async(self) -> None:
        """Run organization in background"""
        try:
            import subprocess
            import asyncio

            # Get current paths
            source_input = self.query_one("#source_directory_input", Input)
            output_input = self.query_one("#output_directory_input", Input)
            source_path = source_input.value or self.source_path
            output_path = output_input.value or self.output_path

            # Update progress
            progress_bar = self.query_one("#progress_bar", ProgressBar)
            progress_bar.update(progress=25)
            self.update_status("Scanning files...")

            # Run the master organization script
            cmd = [
                sys.executable,
                str(Path(__file__).parent / "master_organization_example.py"),
                "--source", source_path,
                "--output", output_path
            ]

            self.log_message(f"Running: {' '.join(cmd)}")

            # Run in subprocess to capture output
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(Path(__file__).parent)
            )

            # Read output line by line
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                line_text = line.decode().strip()
                if line_text:
                    self.log_message(line_text)

                    # Update progress based on log messages
                    if "Scanning" in line_text:
                        progress_bar.update(progress=30)
                        self.update_status("Scanning files...")
                    elif "Processing" in line_text:
                        progress_bar.update(progress=50)
                        self.update_status("Processing files...")
                    elif "Planning" in line_text:
                        progress_bar.update(progress=70)
                        self.update_status("Planning organization...")
                    elif "Executing" in line_text:
                        progress_bar.update(progress=90)
                        self.update_status("Executing moves...")
                    elif "complete" in line_text.lower():
                        progress_bar.update(progress=100)
                        self.update_status("Organization complete!")

            await process.wait()

            if process.returncode == 0:
                self.log_message("✅ Organization completed successfully!")
                self.update_status("Organization complete!")
            else:
                self.log_message(f"❌ Organization failed with code {process.returncode}")
                self.update_status("Organization failed")

        except Exception as e:
            self.log_message(f"❌ Organization error: {e}")
            self.update_status("Organization failed")
        finally:
            self.reset_buttons()

    async def stop_organization(self) -> None:
        """Stop the running organization process"""
        if self.processor:
            self.log_message("🛑 Stopping organization...")
            # In a real implementation, you'd signal the processor to stop
            self.update_status("Stopping...")
            self.reset_buttons()

    def reset_buttons(self) -> None:
        """Reset button states"""
        self._is_running = False
        run_btn = self.query_one("#run_btn", Button)
        stop_btn = self.query_one("#stop_btn", Button)
        run_btn.disabled = False
        stop_btn.disabled = True

    def update_status(self, status: str) -> None:
        """Update status text"""
        status_text = self.query_one("#status_text", Static)
        status_text.update(status)

    def log_message(self, message: str) -> None:
        """Add message to log"""
        log_textarea = self.query_one("#log_textarea", RichLog)
        log_textarea.write(message)

    async def action_show_help(self) -> None:
        """Show help dialog"""
        help_text = """
File Organizer GUI Help

Navigation:
- Use Tab to move between fields
- Enter to activate buttons
- Ctrl+C to quit

Features:
- Source Directory: Where your files are currently located
- Output Directory: Where organized files will be placed
- Preview: Shows what would happen without making changes
- Run Organization: Executes the full organization process

Configuration:
- Load Config: Load settings from file
- Save Config: Save current settings
- Reset: Return to default settings

The organization process uses AI (DeepSeek) to intelligently categorize,
rename, and organize your files based on their content and metadata.
        """
        self.log_message("Help: " + help_text.replace('\n', ' | '))


def main():
    """Main entry point"""
    app = OrganizationGUI()
    app.run()


if __name__ == "__main__":
    main()