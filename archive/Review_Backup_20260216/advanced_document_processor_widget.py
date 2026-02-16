# advanced_document_processor_widget.py

"""
Advanced document processing interface with comprehensive options for model selection,
input/output directory management, and analytics configuration.
"""

import os
import json
import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QFileDialog, 
                             QLabel, QTableWidget, QTableWidgetItem, QHBoxLayout,
                             QMessageBox, QProgressBar, QListWidget, QListWidgetItem,
                             QComboBox, QCheckBox, QGroupBox, QGridLayout, QLineEdit,
                             QTabWidget, QSplitter, QTextEdit, QSpinBox, QDoubleSpinBox,
                             QRadioButton, QButtonGroup, QScrollArea, QSizePolicy, QFrame)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QFont, QIcon, QColor, QPalette

logger = logging.getLogger(__name__)

# Constants
MODEL_OPTIONS = {
    "X.ai Models": [
        "gpt-4-turbo",
        "gpt-4-vision",
        "claude-3-opus",
        "claude-3-sonnet",
        "claude-3-haiku",
        "llama-3-70b",
        "llama-3-8b",
        "gemini-pro",
        "mixtral-8x7b"
    ],
    "Local Models": [
        "local-llama-7b",
        "local-mistral-7b",
        "local-pythia-12b",
        "local-phi-3"
    ]
}

ANALYTICS_OPTIONS = [
    {"name": "Entity Extraction", "description": "Extract named entities like people, organizations, locations, etc."},
    {"name": "Sentiment Analysis", "description": "Analyze the sentiment (positive/negative/neutral) of documents"},
    {"name": "Topic Modeling", "description": "Identify main topics across document collections"},
    {"name": "Key Phrase Extraction", "description": "Extract important phrases and keywords"},
    {"name": "Document Summarization", "description": "Generate concise summaries of documents"},
    {"name": "Content Classification", "description": "Classify documents into predefined categories"},
    {"name": "Relationship Extraction", "description": "Identify relationships between entities"},
    {"name": "Citation Network", "description": "Build citation network graphs from academic documents"},
    {"name": "Timeline Generation", "description": "Generate chronological timelines from events in documents"},
    {"name": "Contradiction Detection", "description": "Identify contradictory statements across document sets"},
    {"name": "Claim Verification", "description": "Verify factual claims against knowledge base"},
    {"name": "Custom Pattern Matching", "description": "Define and search for custom patterns in documents"}
]

class BatchProcessingThread(QThread):
    """Thread for processing documents in the background with advanced options."""
    update_progress = pyqtSignal(int, str)
    processing_complete = pyqtSignal(list, dict)
    processing_error = pyqtSignal(str)
    log_message = pyqtSignal(str)
    
    def __init__(self, document_processor, config):
        super().__init__()
        self.document_processor = document_processor
        self.config = config
    
    def run(self):
        try:
            self.log_message.emit("Starting batch processing with configuration:")
            self.log_message.emit(f"Model: {self.config['model']}")
            self.log_message.emit(f"Analytics: {', '.join(self.config['analytics'])}")
            
            # Get all files to process
            file_paths = []
            if self.config['input_type'] == 'files':
                file_paths = self.config['input_files']
            else:  # input_type == 'directory'
                for root, _, files in os.walk(self.config['input_directory']):
                    for file in files:
                        if self._should_process_file(file):
                            file_paths.append(os.path.join(root, file))
            
            self.log_message.emit(f"Found {len(file_paths)} files to process")
            
            processed_files = []
            analytics_results = {
                "entity_counts": {},
                "sentiment_scores": {},
                "topics": [],
                "summaries": {}
            }
            
            total_files = len(file_paths)
            for i, file_path in enumerate(file_paths):
                try:
                    filename = os.path.basename(file_path)
                    self.log_message.emit(f"Processing file: {filename}")
                    
                    # Process the document with selected options
                    self.update_progress.emit(int((i / total_files) * 100), f"Processing {filename}...")
                    
                    # Simulate advanced processing with different analytics
                    results = self._process_file_with_options(file_path)
                    
                    # Update analytics results
                    self._update_analytics_results(analytics_results, file_path, results)
                    
                    processed_files.append({
                        "path": file_path, 
                        "status": "Processed",
                        "analytics": results
                    })
                    
                except Exception as e:
                    error_msg = f"Error processing {os.path.basename(file_path)}: {str(e)}"
                    self.log_message.emit(error_msg)
                    processed_files.append({"path": file_path, "status": f"Error: {str(e)}"})
                
                # Update progress
                progress = int((i + 1) / total_files * 100)
                self.update_progress.emit(progress, f"Processed {i+1}/{total_files} files")
            
            # Finalize analytics results
            if "Document Summarization" in self.config['analytics']:
                self.log_message.emit("Generating document summaries...")
                # Summaries would be generated here
            
            if "Relationship Extraction" in self.config['analytics']:
                self.log_message.emit("Extracting relationships between entities...")
                # Relationship extraction would happen here
            
            # Export results to output directory if specified
            if self.config['output_directory']:
                self._export_results(processed_files, analytics_results)
            
            self.log_message.emit("Processing complete!")
            self.processing_complete.emit(processed_files, analytics_results)
            
        except Exception as e:
            self.log_message.emit(f"Critical error during processing: {str(e)}")
            self.processing_error.emit(str(e))
    
    def _should_process_file(self, filename):
        """Determine if file should be processed based on extension."""
        extensions = self.config.get('file_extensions', ['.pdf', '.docx', '.txt', '.md'])
        return any(filename.lower().endswith(ext) for ext in extensions)
    
    def _process_file_with_options(self, file_path):
        """Process a file with the selected analytics options."""
        # Simulate processing with different analytics
        results = {}
        filename = os.path.basename(file_path)
        
        # For demonstration - in real implementation, these would call actual methods
        if "Entity Extraction" in self.config['analytics']:
            self.log_message.emit(f"Extracting entities from {filename}...")
            # Simulate entity extraction
            results["entities"] = {
                "people": ["John Smith", "Jane Doe"],
                "organizations": ["Acme Corp", "Global Industries"],
                "locations": ["New York", "London"]
            }
        
        if "Sentiment Analysis" in self.config['analytics']:
            self.log_message.emit(f"Analyzing sentiment in {filename}...")
            # Simulate sentiment analysis
            results["sentiment"] = {
                "score": 0.75,  # Range from -1 to 1
                "label": "Positive"
            }
        
        if "Topic Modeling" in self.config['analytics']:
            self.log_message.emit(f"Extracting topics from {filename}...")
            # Simulate topic modeling
            results["topics"] = [
                {"name": "Business", "confidence": 0.85},
                {"name": "Technology", "confidence": 0.65}
            ]
        
        if "Document Summarization" in self.config['analytics']:
            self.log_message.emit(f"Generating summary for {filename}...")
            # Simulate document summarization
            results["summary"] = "This document discusses the implementation of advanced AI models in business contexts."
        
        # In real implementation, this would be populated by actual document processor results
        return results
    
    def _update_analytics_results(self, analytics_results, file_path, file_results):
        """Update the global analytics results with file-specific results."""
        filename = os.path.basename(file_path)
        
        # Update entity counts
        if "entities" in file_results:
            for entity_type, entities in file_results["entities"].items():
                if entity_type not in analytics_results["entity_counts"]:
                    analytics_results["entity_counts"][entity_type] = {}
                
                for entity in entities:
                    if entity not in analytics_results["entity_counts"][entity_type]:
                        analytics_results["entity_counts"][entity_type][entity] = 0
                    analytics_results["entity_counts"][entity_type][entity] += 1
        
        # Update sentiment scores
        if "sentiment" in file_results:
            analytics_results["sentiment_scores"][filename] = file_results["sentiment"]["score"]
        
        # Update topics
        if "topics" in file_results:
            for topic in file_results["topics"]:
                if topic["name"] not in [t["name"] for t in analytics_results["topics"]]:
                    analytics_results["topics"].append(topic)
        
        # Update summaries
        if "summary" in file_results:
            analytics_results["summaries"][filename] = file_results["summary"]
    
    def _export_results(self, processed_files, analytics_results):
        """Export processing results to the output directory."""
        try:
            output_dir = self.config['output_directory']
            os.makedirs(output_dir, exist_ok=True)
            
            # Save processing summary
            summary_path = os.path.join(output_dir, "processing_summary.json")
            with open(summary_path, 'w') as f:
                json.dump({
                    "config": self.config,
                    "processed_files": processed_files,
                    "analytics_results": analytics_results
                }, f, indent=2)
            
            self.log_message.emit(f"Exported processing summary to {summary_path}")
            
            # Export analytics visualizations
            if "Entity Extraction" in self.config['analytics']:
                # Would generate entity visualization here
                entity_path = os.path.join(output_dir, "entity_analysis.json")
                with open(entity_path, 'w') as f:
                    json.dump(analytics_results["entity_counts"], f, indent=2)
                self.log_message.emit(f"Exported entity analysis to {entity_path}")
            
            if "Sentiment Analysis" in self.config['analytics']:
                # Would generate sentiment visualization here
                sentiment_path = os.path.join(output_dir, "sentiment_analysis.json")
                with open(sentiment_path, 'w') as f:
                    json.dump(analytics_results["sentiment_scores"], f, indent=2)
                self.log_message.emit(f"Exported sentiment analysis to {sentiment_path}")
            
            # Additional exports would be implemented here for other analytics
            
        except Exception as e:
            self.log_message.emit(f"Error exporting results: {str(e)}")

class AdvancedDocumentProcessorWidget(QWidget):
    def __init__(self, document_processor, parent=None):
        """
        Initialize the advanced document processor widget.
        
        :param document_processor: The DocumentProcessor instance to use for processing.
        :param parent: Optional parent widget.
        """
        super().__init__(parent)
        self.document_processor = document_processor
        self.processing_thread = None
        self.selected_files = []
        self.selected_directory = ""
        self.output_directory = ""
        self.current_model = MODEL_OPTIONS["X.ai Models"][0]  # Default model
        self.selected_analytics = []  # Selected analytics options
        
        self._setup_ui()
        logger.info("AdvancedDocumentProcessorWidget initialized.")
    
    def _setup_ui(self):
        """
        Set up the user interface for the advanced document processor.
        """
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        
        # Title
        title_label = QLabel("Advanced Document Processing")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Main content area with tabs
        tab_widget = QTabWidget()
        
        # Configuration tab
        config_tab = QWidget()
        config_layout = QVBoxLayout(config_tab)
        
        # Input Configuration
        input_group = self._create_input_group()
        config_layout.addWidget(input_group)
        
        # Model Selection
        model_group = self._create_model_selection_group()
        config_layout.addWidget(model_group)
        
        # Analytics Options
        analytics_group = self._create_analytics_group()
        config_layout.addWidget(analytics_group)
        
        # Output Configuration
        output_group = self._create_output_group()
        config_layout.addWidget(output_group)
        
        # Add spacer at the bottom
        config_layout.addStretch()
        
        # Files tab
        files_tab = QWidget()
        files_layout = QVBoxLayout(files_tab)
        
        # Files table
        self.files_table = QTableWidget()
        self.files_table.setColumnCount(3)
        self.files_table.setHorizontalHeaderLabels(["Filename", "Path", "Status"])
        self.files_table.horizontalHeader().setStretchLastSection(True)
        self.files_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        files_layout.addWidget(self.files_table)
        
        # Log tab
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        log_layout.addWidget(self.log_display)
        
        # Results tab
        results_tab = QWidget()
        results_layout = QVBoxLayout(results_tab)
        
        self.results_view = QTextEdit()
        self.results_view.setReadOnly(True)
        results_layout.addWidget(self.results_view)
        
        # Add tabs to tab widget
        tab_widget.addTab(config_tab, "Configuration")
        tab_widget.addTab(files_tab, "Files")
        tab_widget.addTab(log_tab, "Processing Log")
        tab_widget.addTab(results_tab, "Results")
        
        main_layout.addWidget(tab_widget)
        
        # Progress bar
        progress_frame = QFrame()
        progress_layout = QHBoxLayout(progress_frame)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_status = QLabel("Ready")
        
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_status)
        
        main_layout.addWidget(progress_frame)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.process_button = QPushButton("Process Documents")
        self.process_button.setMinimumHeight(40)  # Taller button
        self.process_button.clicked.connect(self._start_processing)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._cancel_processing)
        self.cancel_button.setEnabled(False)
        
        button_layout.addWidget(self.process_button)
        button_layout.addWidget(self.cancel_button)
        
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
        self.resize(900, 700)  # Default size
        
        # Initialize log
        self._log_message("System ready. Configure processing options and select files to begin.")
    
    def _create_input_group(self):
        """
        Create the input configuration group.
        """
        group_box = QGroupBox("Input Configuration")
        layout = QVBoxLayout()
        
        # Input type selection
        input_type_layout = QHBoxLayout()
        self.file_radio = QRadioButton("Select Files")
        self.directory_radio = QRadioButton("Select Directory")
        self.file_radio.setChecked(True)  # Default to file selection
        
        input_type_group = QButtonGroup()
        input_type_group.addButton(self.file_radio)
        input_type_group.addButton(self.directory_radio)
        
        input_type_layout.addWidget(self.file_radio)
        input_type_layout.addWidget(self.directory_radio)
        input_type_layout.addStretch()
        
        layout.addLayout(input_type_layout)
        
        # File selection
        file_layout = QHBoxLayout()
        self.file_path_display = QLineEdit()
        self.file_path_display.setReadOnly(True)
        self.file_path_display.setPlaceholderText("No files selected")
        
        self.select_files_button = QPushButton("Browse...")
        self.select_files_button.clicked.connect(self._select_files)
        
        file_layout.addWidget(self.file_path_display)
        file_layout.addWidget(self.select_files_button)
        
        layout.addLayout(file_layout)
        
        # File type filters
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("File Types:"))
        
        self.pdf_check = QCheckBox("PDF")
        self.pdf_check.setChecked(True)
        self.docx_check = QCheckBox("DOCX/DOC")
        self.docx_check.setChecked(True)
        self.txt_check = QCheckBox("TXT")
        self.txt_check.setChecked(True)
        self.other_check = QCheckBox("Other")
        
        filter_layout.addWidget(self.pdf_check)
        filter_layout.addWidget(self.docx_check)
        filter_layout.addWidget(self.txt_check)
        filter_layout.addWidget(self.other_check)
        filter_layout.addStretch()
        
        layout.addLayout(filter_layout)
        
        group_box.setLayout(layout)
        return group_box
    
    def _create_model_selection_group(self):
        """
        Create the model selection group.
        """
        group_box = QGroupBox("Model Selection")
        layout = QVBoxLayout()
        
        # Model category selection
        category_layout = QHBoxLayout()
        category_layout.addWidget(QLabel("Model Provider:"))
        
        self.model_category = QComboBox()
        for category in MODEL_OPTIONS.keys():
            self.model_category.addItem(category)
        self.model_category.currentTextChanged.connect(self._update_model_options)
        
        category_layout.addWidget(self.model_category)
        category_layout.addStretch()
        
        layout.addLayout(category_layout)
        
        # Model selection
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model:"))
        
        self.model_selector = QComboBox()
        self._update_model_options(list(MODEL_OPTIONS.keys())[0])
        
        model_layout.addWidget(self.model_selector)
        model_layout.addStretch()
        
        layout.addLayout(model_layout)
        
        # Advanced model options
        advanced_layout = QGridLayout()
        
        # Temperature
        advanced_layout.addWidget(QLabel("Temperature:"), 0, 0)
        self.temperature_spinner = QDoubleSpinBox()
        self.temperature_spinner.setRange(0.0, 2.0)
        self.temperature_spinner.setSingleStep(0.1)
        self.temperature_spinner.setValue(0.7)
        advanced_layout.addWidget(self.temperature_spinner, 0, 1)
        
        # Max tokens
        advanced_layout.addWidget(QLabel("Max Tokens:"), 0, 2)
        self.max_tokens_spinner = QSpinBox()
        self.max_tokens_spinner.setRange(1, 100000)
        self.max_tokens_spinner.setSingleStep(100)
        self.max_tokens_spinner.setValue(2000)
        advanced_layout.addWidget(self.max_tokens_spinner, 0, 3)
        
        # Top P
        advanced_layout.addWidget(QLabel("Top P:"), 1, 0)
        self.top_p_spinner = QDoubleSpinBox()
        self.top_p_spinner.setRange(0.0, 1.0)
        self.top_p_spinner.setSingleStep(0.05)
        self.top_p_spinner.setValue(0.95)
        advanced_layout.addWidget(self.top_p_spinner, 1, 1)
        
        # API Key (hidden by default)
        self.api_key_check = QCheckBox("Custom API Key")
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setEnabled(False)
        self.api_key_check.toggled.connect(self.api_key_edit.setEnabled)
        
        advanced_layout.addWidget(self.api_key_check, 1, 2)
        advanced_layout.addWidget(self.api_key_edit, 1, 3)
        
        layout.addLayout(advanced_layout)
        
        group_box.setLayout(layout)
        return group_box
    
    def _create_analytics_group(self):
        """
        Create the analytics options group.
        """
        group_box = QGroupBox("Analytics Configuration")
        layout = QVBoxLayout()
        
        # Create scrollable area for analytics options
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # Add analytics options with descriptions
        for option in ANALYTICS_OPTIONS:
            option_checkbox = QCheckBox(option["name"])
            option_checkbox.setToolTip(option["description"])
            
            # Connect the checkbox to the analytics selection handler
            option_checkbox.stateChanged.connect(
                lambda state, name=option["name"]: self._handle_analytics_selection(state, name)
            )
            
            scroll_layout.addWidget(option_checkbox)
        
        scroll_layout.addStretch()
        scroll_content.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_content)
        
        layout.addWidget(scroll_area)
        
        # Analytics parameters
        params_layout = QGridLayout()
        
        # Entity types to extract
        params_layout.addWidget(QLabel("Entity Types:"), 0, 0)
        entity_layout = QHBoxLayout()
        self.entity_people = QCheckBox("People")
        self.entity_people.setChecked(True)
        self.entity_orgs = QCheckBox("Organizations")
        self.entity_orgs.setChecked(True)
        self.entity_locations = QCheckBox("Locations")
        self.entity_locations.setChecked(True)
        self.entity_dates = QCheckBox("Dates")
        self.entity_dates.setChecked(True)
        
        entity_layout.addWidget(self.entity_people)
        entity_layout.addWidget(self.entity_orgs)
        entity_layout.addWidget(self.entity_locations)
        entity_layout.addWidget(self.entity_dates)
        entity_layout.addStretch()
        
        params_widget = QWidget()
        params_widget.setLayout(entity_layout)
        params_layout.addWidget(params_widget, 0, 1)
        
        # Summary length
        params_layout.addWidget(QLabel("Summary Length:"), 1, 0)
        self.summary_length = QComboBox()
        self.summary_length.addItems(["Short", "Medium", "Long"])
        self.summary_length.setCurrentIndex(1)  # Default to Medium
        params_layout.addWidget(self.summary_length, 1, 1)
        
        layout.addLayout(params_layout)
        
        group_box.setLayout(layout)
        return group_box
    
    def _create_output_group(self):
        """
        Create the output configuration group.
        """
        group_box = QGroupBox("Output Configuration")
        layout = QVBoxLayout()
        
        # Output directory
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("Output Directory:"))
        
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setReadOnly(True)
        self.output_dir_edit.setPlaceholderText("No output directory selected")
        
        self.output_dir_button = QPushButton("Browse...")
        self.output_dir_button.clicked.connect(self._select_output_directory)
        
        dir_layout.addWidget(self.output_dir_edit)
        dir_layout.addWidget(self.output_dir_button)
        
        layout.addLayout(dir_layout)
        
        # Output options
        options_layout = QVBoxLayout()
        
        self.json_check = QCheckBox("Export JSON Results")
        self.json_check.setChecked(True)
        options_layout.addWidget(self.json_check)
        
        self.csv_check = QCheckBox("Export CSV Data")
        self.csv_check.setChecked(True)
        options_layout.addWidget(self.csv_check)
        
        self.html_check = QCheckBox("Generate HTML Report")
        self.html_check.setChecked(True)
        options_layout.addWidget(self.html_check)
        
        self.visualize_check = QCheckBox("Generate Visualizations")
        self.visualize_check.setChecked(True)
        options_layout.addWidget(self.visualize_check)
        
        layout.addLayout(options_layout)
        
        group_box.setLayout(layout)
        return group_box
    
    def _update_model_options(self, category):
        """
        Update the model options based on the selected category.
        
        :param category: The selected model category.
        """
        self.model_selector.clear()
        self.model_selector.addItems(MODEL_OPTIONS[category])
        self.current_model = self.model_selector.currentText()
    
    def _handle_analytics_selection(self, state, name):
        """
        Handle changes in analytics selection.
        
        :param state: The checkbox state.
        :param name: The name of the analytics option.
        """
        if state == Qt.CheckState.Checked.value:
            if name not in self.selected_analytics:
                self.selected_analytics.append(name)
        else:
            if name in self.selected_analytics:
                self.selected_analytics.remove(name)
    
    def _select_files(self):
        """
        Open a file dialog to select multiple files for processing.
        """
        if self.file_radio.isChecked():
            # Build the file filter string based on checkboxes
            file_filters = []
            if self.pdf_check.isChecked():
                file_filters.append("PDF Files (*.pdf)")
            if self.docx_check.isChecked():
                file_filters.append("Word Documents (*.docx *.doc)")
            if self.txt_check.isChecked():
                file_filters.append("Text Files (*.txt)")
            if self.other_check.isChecked():
                file_filters.append("Other Files (*.*)")
            
            # Create a combined filter
            combined_filter = ";;".
            options = QFileDialog.Options()
            file_paths, _ = QFileDialog.getOpenFileNames(
                self, 
                "Select Documents to Process", 
                "", 
                ";;".
                options=options
            )
            
            if file_paths:
                self.selected_files = file_paths
                self.file_path_display.setText(f"{len(file_paths)} files selected")
                self._update_files_table(file_paths)
                self._log_message(f"Selected {len(file_paths)} files for processing.")
        else:  # Directory selection
            directory = QFileDialog.getExistingDirectory(
                self,
                "Select Directory to Process",
                ""
            )
            
            if directory:
                self.selected_directory = directory
                self.file_path_display.setText(directory)
                self._scan_directory(directory)
                self._log_message(f"Selected directory: {directory}")
    
    def _scan_directory(self, directory):
        """
        Scan the selected directory for files matching the selected extensions.
        
        :param directory: The directory to scan.
        """
        extensions = []
        if self.pdf_check.isChecked():
            extensions.append(".pdf")
        if self.docx_check.isChecked():
            extensions.extend([".docx", ".doc"])
        if self.txt_check.isChecked():
            extensions.append(".txt")
        if self.other_check.isChecked():
            extensions.extend([".md", ".rtf", ".csv", ".json"])
        
        files = []
        for root, _, filenames in os.walk(directory):
            for filename in filenames:
                if any(filename.lower().endswith(ext) for ext in extensions):
                    files.append(os.path.join(root, filename))
        
        self._update_files_table(files)
        self._log_message(f"Found {len(files)} matching files in directory.")
    
    def _select_output_directory(self):
        """
        Open a directory dialog to select the output directory.
        """
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            ""
        )
        
        if directory:
            self.output_directory = directory
            self.output_dir_edit.setText(directory)
            self._log_message(f"Output directory set to: {directory}")
    
    def _update_files_table(self, files):
        """
        Update the files table with the selected files.
        
        :param files: List of file paths.
        """
        self.files_table.setRowCount(len(files))
        
        for i, file_path in enumerate(files):
            filename = os.path.basename(file_path)
            
            # Filename
            filename_item = QTableWidgetItem(filename)
            filename_item.setFlags(filename_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.files_table.setItem(i, 0, filename_item)
            
            # Path
            path_item = QTableWidgetItem(file_path)
            path_item.setFlags(path_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.files_table.setItem(i, 1, path_item)
            
            # Status
            status_item = QTableWidgetItem("Pending")
            self.files_table.setItem(i, 2, status_item)
        
        self.files_table.resizeColumnsToContents()
    
    def _start_processing(self):
        """
        Start the document processing with the configured options.
        """
        # Get the selected model
        self.current_model = self.model_selector.currentText()
        
        # Update UI state
        self.process_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_status.setText("Initializing...")
        
        # Collect file extensions for filtering
        extensions = []
        if self.pdf_check.isChecked():
            extensions.append(".pdf")
        if self.docx_check.isChecked():
            extensions.extend([".docx", ".doc"])
        if self.txt_check.isChecked():
            extensions.append(".txt")
        if self.other_check.isChecked():
            extensions.extend([".md", ".rtf", ".csv", ".json"])
        
        # Build processing configuration
        config = {
            "model": self.current_model,
            "analytics": self.selected_analytics,
            "file_extensions": extensions,
            "output_directory": self.output_directory,
            "model_params": {
                "temperature": self.temperature_spinner.value(),
                "max_tokens": self.max_tokens_spinner.value(),
                "top_p": self.top_p_spinner.value()
            },
            "output_formats": {
                "json": self.json_check.isChecked(),
                "csv": self.csv_check.isChecked(),
                "html": self.html_check.isChecked(),
                "visualizations": self.visualize_check.isChecked()
            },
            "entity_types": {
                "people": self.entity_people.isChecked(),
                "organizations": self.entity_orgs.isChecked(),
                "locations": self.entity_locations.isChecked(),
                "dates": self.entity_dates.isChecked()
            },
            "summary_length": self.summary_length.currentText().lower()
        }
        
        # Set input files or directory
        if self.file_radio.isChecked():
            config["input_type"] = "files"
            config["input_files"] = self.selected_files
            if not self.selected_files:
                QMessageBox.warning(self, "No Files Selected", "Please select at least one file to process.")
                self._reset_processing_ui()
                return
        else:  # Directory selection
            config["input_type"] = "directory"
            config["input_directory"] = self.selected_directory
            if not self.selected_directory:
                QMessageBox.warning(self, "No Directory Selected", "Please select a directory to process.")
                self._reset_processing_ui()
                return
        
        # Check if output directory is set
        if not self.output_directory and (self.json_check.isChecked() or self.csv_check.isChecked() or 
                                         self.html_check.isChecked() or self.visualize_check.isChecked()):
            QMessageBox.warning(self, "No Output Directory", "Please select an output directory for the results.")
            self._reset_processing_ui()
            return
        
        # Check if any analytics are selected
        if not self.selected_analytics:
            QMessageBox.warning(self, "No Analytics Selected", "Please select at least one analytics option.")
            self._reset_processing_ui()
            return
        
        # Start processing thread
        self._log_message("Starting document processing with the following configuration:")
        self._log_message(f"Model: {self.current_model}")
        self._log_message(f"Analytics: {', '.join(self.selected_analytics)}")
        self._log_message(f"Output Directory: {self.output_directory if self.output_directory else 'Not set'}")
        
        # Clear the results view
        self.results_view.clear()
        
        self.processing_thread = BatchProcessingThread(self.document_processor, config)
        self.processing_thread.update_progress.connect(self._update_progress)
        self.processing_thread.processing_complete.connect(self._processing_complete)
        self.processing_thread.processing_error.connect(self._processing_error)
        self.processing_thread.log_message.connect(self._log_message)
        self.processing_thread.start()
    
    def _cancel_processing(self):
        """
        Cancel the current processing operation.
        """
        if self.processing_thread and self.processing_thread.isRunning():
            self.processing_thread.terminate()
            self._log_message("Processing cancelled by user.")
            self._reset_processing_ui()
    
    def _update_progress(self, value, status):
        """
        Update the progress bar and status.
        
        :param value: The progress value (0-100).
        :param status: The status message.
        """
        self.progress_bar.setValue(value)
        self.progress_status.setText(status)
    
    def _processing_complete(self, files_results, analytics_results):
        """
        Handle completion of processing.
        
        :param files_results: Results for each processed file.
        :param analytics_results: Combined analytics results.
        """
        self._log_message("Processing completed successfully!")
        
        # Update file status in the table
        for i in range(self.files_table.rowCount()):
            file_path = self.files_table.item(i, 1).text()
            
            # Find the corresponding result
            for result in files_results:
                if result["path"] == file_path:
                    self.files_table.item(i, 2).setText(result["status"])
                    break
        
        # Show summary in results view
        summary = "Processing Summary:\n\n"
        
        # Files processed
        summary += f"Files Processed: {len(files_results)}\n"
        successful = sum(1 for result in files_results if result["status"] == "Processed")
        summary += f"Successfully Processed: {successful}\n"
        failed = len(files_results) - successful
        summary += f"Failed: {failed}\n\n"
        
        # Analytics summary
        summary += "Analytics Results:\n\n"
        
        if analytics_results["entity_counts"]:
            summary += "Entities Extracted:\n"
            for entity_type, entities in analytics_results["entity_counts"].items():
                summary += f"  {entity_type.capitalize()}: {len(entities)} unique entities\n"
            summary += "\n"
        
        if analytics_results["topics"]:
            summary += "Main Topics Identified:\n"
            for topic in analytics_results["topics"]:
                summary += f"  {topic['name']} (confidence: {topic['confidence']:.2f})\n"
            summary += "\n"
        
        if analytics_results["sentiment_scores"]:
            # Calculate average sentiment
            avg_sentiment = sum(analytics_results["sentiment_scores"].values()) / len(analytics_results["sentiment_scores"])
            sentiment_label = "Positive" if avg_sentiment > 0.3 else "Neutral" if avg_sentiment > -0.3 else "Negative"
            summary += f"Average Sentiment: {sentiment_label} ({avg_sentiment:.2f})\n\n"
        
        if self.output_directory:
            summary += f"Results exported to: {self.output_directory}\n"
        
        self.results_view.setPlainText(summary)
        
        # Reset UI
        self._reset_processing_ui()
        
        QMessageBox.information(self, "Processing Complete", 
                               f"Successfully processed {successful} out of {len(files_results)} files.")
    
    def _processing_error(self, error_msg):
        """
        Handle processing errors.
        
        :param error_msg: The error message.
        """
        self._log_message(f"Error during processing: {error_msg}")
        self._reset_processing_ui()
        
        QMessageBox.critical(self, "Processing Error", 
                            f"An error occurred during processing: {error_msg}")
    
    def _reset_processing_ui(self):
        """
        Reset the UI after processing completes or is cancelled.
        """
        self.process_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress_status.setText("Ready")
    
    def _log_message(self, message):
        """
        Add a message to the log display.
        
        :param message: The message to log.
        """
        self.log_display.append(message)
        # Auto-scroll to the bottom
        scroll_bar = self.log_display.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())