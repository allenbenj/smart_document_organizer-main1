"""
NLP Model Manager Dialog

Provides UI for installing and managing NLP model libraries:
- spaCy language models  
- GLiNER entity recognition models
- Transformers models from Hugging Face

Features:
- Model selection checkboxes
- Download progress tracking
- Model validation
- Storage location management
"""

import os
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
import subprocess
import threading

try:
    from PySide6.QtWidgets import (
        QDialog,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QCheckBox,
        QGroupBox,
        QProgressBar,
        QTextEdit,
        QComboBox,
        QLineEdit,
        QFileDialog,
        QMessageBox,
        QListWidget,
        QListWidgetItem,
        QScrollArea,
        QWidget,
        QFrame,
    )
    from PySide6.QtCore import Qt, Signal, QThread, Slot
    from PySide6.QtGui import QFont
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QDialog = Any = object  # type: ignore


class ModelDownloadWorker(QThread):  # type: ignore[misc]
    """Background worker for downloading models."""
    
    # Signals
    progress = Signal(str)  # type: ignore[misc]
    finished = Signal(bool, str)  # type: ignore[misc] - success, message
    
    def __init__(self, model_type: str, model_name: str, python_executable: str):
        super().__init__()
        self.model_type = model_type
        self.model_name = model_name
        self.python_executable = python_executable
    
    def run(self):
        """Download and install the model."""
        try:
            if self.model_type == 'spacy':
                self.install_spacy_model()
            elif self.model_type == 'gliner':
                self.install_gliner_model()
            elif self.model_type == 'transformers':
                self.install_transformers_model()
            else:
                self.finished.emit(False, f"Unknown model type: {self.model_type}")
        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}")
    
    def install_spacy_model(self):
        """Install a spaCy language model."""
        self.progress.emit(f"Installing spaCy package...")
        
        # Install spacy if not already installed
        result = subprocess.run(
            [self.python_executable, '-m', 'pip', 'install', 'spacy'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            self.finished.emit(False, f"Failed to install spacy: {result.stderr}")
            return
        
        # Download the language model
        self.progress.emit(f"Downloading spaCy model: {self.model_name}...")
        
        result = subprocess.run(
            [self.python_executable, '-m', 'spacy', 'download', self.model_name],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            self.finished.emit(True, f"Successfully installed spaCy model: {self.model_name}")
        else:
            self.finished.emit(False, f"Failed to download model: {result.stderr}")
    
    def install_gliner_model(self):
        """Install GLiNER package and download model."""
        self.progress.emit(f"Installing GLiNER package...")
        
        # Install gliner
        result = subprocess.run(
            [self.python_executable, '-m', 'pip', 'install', 'gliner'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            self.finished.emit(False, f"Failed to install GLiNER: {result.stderr}")
            return
        
        # Download model using Python
        self.progress.emit(f"Downloading GLiNER model: {self.model_name}...")
        
        download_script = f"""
from gliner import GLiNER
model = GLiNER.from_pretrained("{self.model_name}")
print("Model downloaded successfully")
"""
        
        result = subprocess.run(
            [self.python_executable, '-c', download_script],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            self.finished.emit(True, f"Successfully installed GLiNER model: {self.model_name}")
        else:
            self.finished.emit(False, f"Failed to download model: {result.stderr}")
    
    def install_transformers_model(self):
        """Install transformers package and download model."""
        self.progress.emit(f"Installing transformers package...")
        
        # Install transformers
        result = subprocess.run(
            [self.python_executable, '-m', 'pip', 'install', 'transformers', 'torch'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            self.finished.emit(False, f"Failed to install transformers: {result.stderr}")
            return
        
        # Download model
        self.progress.emit(f"Downloading Transformers model: {self.model_name}...")
        
        download_script = f"""
from transformers import AutoModel, AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("{self.model_name}")
model = AutoModel.from_pretrained("{self.model_name}")
print("Model downloaded successfully")
"""
        
        result = subprocess.run(
            [self.python_executable, '-c', download_script],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            self.finished.emit(True, f"Successfully installed Transformers model: {self.model_name}")
        else:
            self.finished.emit(False, f"Failed to download model: {result.stderr}")


class NLPModelManagerDialog(QDialog):  # type: ignore[misc]
    """
    Dialog for managing NLP model installations.
    
    Allows users to:
    - Select and download spaCy models (en_core_web_sm, en_core_web_lg, etc.)
    - Select and download GLiNER models
    - Select and download Transformers models
    - View installed models
    - Monitor download progress
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker: Optional[ModelDownloadWorker] = None
        self.python_executable = sys.executable
        self.setup_ui()
        self.load_installed_models()
    
    def setup_ui(self):
        """Setup the user interface."""
        self.setWindowTitle("NLP Model Manager")
        self.setMinimumSize(800, 600)
        
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("NLP Model Manager")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Description
        desc = QLabel(
            "Download and manage NLP models for entity extraction, text analysis, and more. "
            "Select models below and click Install to download."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; padding: 5px 0 10px 0;")
        layout.addWidget(desc)
        
        # Scroll area for model groups
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # spaCy Models
        self.spacy_group = self.create_spacy_group()
        scroll_layout.addWidget(self.spacy_group)
        
        # GLiNER Models
        self.gliner_group = self.create_gliner_group()
        scroll_layout.addWidget(self.gliner_group)
        
        # Transformers Models
        self.transformers_group = self.create_transformers_group()
        scroll_layout.addWidget(self.transformers_group)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        # Progress section
        progress_frame = QFrame()
        progress_frame.setFrameShape(QFrame.StyledPanel)
        progress_layout = QVBoxLayout(progress_frame)
        
        self.progress_label = QLabel("Ready to install models")
        progress_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(100)
        self.log_output.setPlaceholderText("Installation logs will appear here...")
        progress_layout.addWidget(self.log_output)
        
        layout.addWidget(progress_frame)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.install_button = QPushButton("📥 Install Selected Models")
        self.install_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.install_button.clicked.connect(self.install_selected_models)
        button_layout.addWidget(self.install_button)
        
        self.refresh_button = QPushButton("🔄 Refresh Installed")
        self.refresh_button.clicked.connect(self.load_installed_models)
        button_layout.addWidget(self.refresh_button)
        
        button_layout.addStretch()
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
    def create_spacy_group(self) -> QGroupBox:
        """Create spaCy models group."""
        group = QGroupBox("spaCy Language Models")
        layout = QVBoxLayout(group)
        
        desc = QLabel("Industrial-strength NLP with pre-trained models for named entity recognition, POS tagging, etc.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; font-size: 11px; padding-bottom: 5px;")
        layout.addWidget(desc)
        
        self.spacy_checkboxes = {}
        
        models = [
            ("en_core_web_sm", "English - Small (12 MB)", "Basic NER, POS, dependencies"),
            ("en_core_web_md", "English - Medium (40 MB)", "Includes word vectors"),
            ("en_core_web_lg", "English - Large (560 MB)", "Best accuracy, includes word vectors"),
            ("en_core_web_trf", "English - Transformer (440 MB)", "Transformer-based, highest accuracy"),
        ]
        
        for model_name, display_name, description in models:
            checkbox = QCheckBox(f"{display_name}")
            checkbox.setToolTip(description)
            checkbox.setProperty("model_name", model_name)
            self.spacy_checkboxes[model_name] = checkbox
            layout.addWidget(checkbox)
        
        return group
    
    def create_gliner_group(self) -> QGroupBox:
        """Create GLiNER models group."""
        group = QGroupBox("GLiNER Entity Recognition Models")
        layout = QVBoxLayout(group)
        
        desc = QLabel("Generalist model for NER - extracts any entity type without retraining.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; font-size: 11px; padding-bottom: 5px;")
        layout.addWidget(desc)
        
        self.gliner_checkboxes = {}
        
        models = [
            ("urchade/gliner_small", "GLiNER Small (166 MB)", "Fast inference, good accuracy"),
            ("urchade/gliner_medium", "GLiNER Medium (340 MB)", "Balanced speed/accuracy"),
            ("urchade/gliner_large", "GLiNER Large (750 MB)", "Best accuracy"),
        ]
        
        for model_name, display_name, description in models:
            checkbox = QCheckBox(f"{display_name}")
            checkbox.setToolTip(description)
            checkbox.setProperty("model_name", model_name)
            self.gliner_checkboxes[model_name] = checkbox
            layout.addWidget(checkbox)
        
        return group
    
    def create_transformers_group(self) -> QGroupBox:
        """Create Transformers models group."""
        group = QGroupBox("Hugging Face Transformers Models")
        layout = QVBoxLayout(group)
        
        desc = QLabel("Pre-trained transformer models for various NLP tasks.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; font-size: 11px; padding-bottom: 5px;")
        layout.addWidget(desc)
        
        self.transformers_checkboxes = {}
        
        models = [
            ("bert-base-uncased", "BERT Base Uncased (440 MB)", "General purpose text understanding"),
            ("roberta-base", "RoBERTa Base (500 MB)", "Improved BERT variant"),
            ("distilbert-base-uncased", "DistilBERT Base (265 MB)", "Faster, lighter BERT"),
            ("dslim/bert-base-NER", "BERT NER (440 MB)", "Fine-tuned for named entity recognition"),
        ]
        
        for model_name, display_name, description in models:
            checkbox = QCheckBox(f"{display_name}")
            checkbox.setToolTip(description)
            checkbox.setProperty("model_name", model_name)
            self.transformers_checkboxes[model_name] = checkbox
            layout.addWidget(checkbox)
        
        return group
    
    def load_installed_models(self):
        """Check which models are already installed."""
        self.log_output.append("Checking installed models...\n")
        
        # Check spaCy models
        try:
            import spacy
            installed_spacy = spacy.util.get_installed_models()
            for model_name, checkbox in self.spacy_checkboxes.items():
                if model_name in installed_spacy:
                    checkbox.setChecked(False)
                    checkbox.setText(f"{checkbox.text()} ✓ Installed")
                    checkbox.setEnabled(False)
                    checkbox.setStyleSheet("color: green;")
        except ImportError:
            self.log_output.append("spaCy not installed\n")
        
        # Check GLiNER
        try:
            import gliner
            self.log_output.append("GLiNER package installed\n")
        except ImportError:
            self.log_output.append("GLiNER not installed\n")
        
        # Check Transformers
        try:
            import transformers
            self.log_output.append("Transformers package installed\n")
        except ImportError:
            self.log_output.append("Transformers not installed\n")
        
        self.log_output.append("Check complete.\n")
    
    def install_selected_models(self):
        """Install all selected models."""
        selected_models = []
        
        # Collect spacy selections
        for model_name, checkbox in self.spacy_checkboxes.items():
            if checkbox.isChecked():
                selected_models.append(('spacy', model_name))
        
        # Collect gliner selections
        for model_name, checkbox in self.gliner_checkboxes.items():
            if checkbox.isChecked():
                selected_models.append(('gliner', model_name))
        
        # Collect transformers selections
        for model_name, checkbox in self.transformers_checkboxes.items():
            if checkbox.isChecked():
                selected_models.append(('transformers', model_name))
        
        if not selected_models:
            QMessageBox.information(
                self,
                "No Models Selected",
                "Please select at least one model to install."
            )
            return
        
        # Show confirmation
        model_list = "\n".join([f"- {model_type}: {model_name}" 
                                for model_type, model_name in selected_models])
        
        reply = QMessageBox.question(
            self,
            "Confirm Installation",
            f"Install the following models?\n\n{model_list}",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
        
        # Start installation queue
        self.install_queue = selected_models
        self.current_install_index = 0
        self.install_next_model()
    
    def install_next_model(self):
        """Install the next model in the queue."""
        if self.current_install_index >= len(self.install_queue):
            # All done
            self.progress_bar.setVisible(False)
            self.install_button.setEnabled(True)
            self.progress_label.setText("✅ All installations complete!")
            self.log_output.append("\n=== All installations complete ===\n")
            self.load_installed_models()
            return
        
        model_type, model_name = self.install_queue[self.current_install_index]
        
        self.progress_label.setText(f"Installing {model_type}: {model_name}...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.install_button.setEnabled(False)
        
        self.log_output.append(f"\n--- Installing {model_type}: {model_name} ---\n")
        
        # Create and start worker
        self.worker = ModelDownloadWorker(model_type, model_name, self.python_executable)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_installation_finished)
        self.worker.start()
    
    @Slot(str)
    def on_progress(self, message: str):
        """Handle progress updates."""
        self.log_output.append(f"{message}\n")
    
    @Slot(bool, str)
    def on_installation_finished(self, success: bool, message: str):
        """Handle installation completion."""
        if success:
            self.log_output.append(f"✅ {message}\n")
        else:
            self.log_output.append(f"❌ {message}\n")
        
        # Move to next model
        self.current_install_index += 1
        self.install_next_model()


# Standalone test
if __name__ == '__main__':
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    dialog = NLPModelManagerDialog()
    dialog.show()
    sys.exit(app.exec())
