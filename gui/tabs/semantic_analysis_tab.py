"""
Semantic Analysis Tab - AEDIS High-Fidelity Intelligence
Thematic discovery, clustering, and strategic content analysis.
"""

from typing import Optional, Any
import pandas as pd
import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, 
    QPushButton, QComboBox, QCheckBox, QGroupBox, QSplitter, 
    QLineEdit, QMessageBox, QFileDialog, QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView
)

from ..ui import JobStatusWidget, KnowledgeBaseBrowser
from .default_paths import get_default_dialog_dir
from .workers import SemanticAnalysisWorker
from gui.core.base_tab import BaseTab
from gui.services import api_client # Import api_client

logger = logging.getLogger(__name__)

class SemanticAnalysisTab(BaseTab):
    def __init__(self, asyncio_thread: Optional[Any] = None, parent=None):
        super().__init__("Semantic Analysis", asyncio_thread, parent)
        self.last_analysis_result = None  # Store the last result for export
        self.setup_ui()
        # Connect signals for linked memories after UI setup
        self.file_path.textChanged.connect(self._refresh_action_state)
        self.file_path.textChanged.connect(self.load_linked_memories) # Load memories when file path changes
        self.text_input.textChanged.connect(self._refresh_action_state)
        self._refresh_action_state()


    def setup_ui(self):
        """Initializes the semantic analysis tab UI."""
        title = QLabel("Semantic Analysis & Thematic Discovery")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        self.main_layout.addWidget(title)

        quick_help = QLabel(
            "Quick Start: 1) Load from Knowledge Base OR choose a file/text. "
            "2) Click Start Discovery. 3) Review output. 4) Export if needed."
        )
        quick_help.setWordWrap(True)
        quick_help.setStyleSheet("color: #9e9e9e; padding: 4px 0 8px 0;")
        self.main_layout.addWidget(quick_help)
        self.prereq_status = QLabel("")
        self.prereq_status.setWordWrap(True)
        self.prereq_status.setStyleSheet("color: #ffcc80; padding: 0 0 8px 0;")
        self.main_layout.addWidget(self.prereq_status)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_layout.addWidget(self.main_splitter)

        # LEFT: Configuration
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # 1. KB Browser
        kb_group = QGroupBox("1. Load from Knowledge Base")
        kb_layout = QVBoxLayout(kb_group)
        self.kb_browser = KnowledgeBaseBrowser()
        self.kb_browser.document_selected.connect(self.on_kb_document_selected)
        kb_layout.addWidget(self.kb_browser)
        kb_group.setLayout(kb_layout)
        left_layout.addWidget(kb_group)

        # 2. Input
        input_group = QGroupBox("2. Intelligence Input")
        input_layout = QVBoxLayout(input_group)
        
        path_row = QHBoxLayout()
        self.file_path = QLineEdit()
        self.file_path.setPlaceholderText("Select file path...")
        path_row.addWidget(self.file_path)
        self.browse_btn = QPushButton("...")
        self.browse_btn.setMaximumWidth(40)
        self.browse_btn.clicked.connect(self.browse_file)
        path_row.addWidget(self.browse_btn)
        input_layout.addLayout(path_row)

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("Paste text for thematic clustering...")
        self.text_input.setMaximumHeight(150)
        input_layout.addWidget(self.text_input)
        left_layout.addWidget(input_group)

        # 3. Settings
        strategy_group = QGroupBox("3. Analysis Strategy")
        strategy_layout = QVBoxLayout(strategy_group)
        
        self.analysis_combo = QComboBox()
        self.analysis_combo.addItems([
            "Strategic Clustering", "Summarization", "Topic Identification",
            "Sentiment Analysis", "Key Phrases"
        ])
        strategy_layout.addWidget(self.analysis_combo)
        
        self.auto_label = QCheckBox("Auto-Label Themes (KG Prep)")
        self.auto_label.setChecked(True)
        strategy_layout.addWidget(self.auto_label)
        
        self.smoking_gun = QCheckBox("Smoking Gun Detection (Outliers)")
        strategy_layout.addWidget(self.smoking_gun)
        left_layout.addWidget(strategy_group)

        # 4. Action
        self.analyze_btn = QPushButton("⚡ Start Discovery")
        self.analyze_btn.setMinimumHeight(50)
        self.analyze_btn.setStyleSheet("background-color: #1565C0; color: white; font-weight: bold; font-size: 14px;")
        self.analyze_btn.clicked.connect(self.analyze_document)
        left_layout.addWidget(self.analyze_btn)
        
        left_layout.addStretch()
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(left_widget)
        self.main_splitter.addWidget(scroll)

        # RIGHT: Results
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        right_layout.addWidget(self.results_text)

        self.discover_btn_right = QPushButton("⚡ Start Discovery")
        self.discover_btn_right.setStyleSheet(
            "background-color: #1565C0; color: white; font-weight: bold; font-size: 14px;"
        )
        self.discover_btn_right.clicked.connect(self.analyze_document)
        right_layout.addWidget(self.discover_btn_right)

        # Export to Excel Button
        self.export_btn = QPushButton("Export to Excel")
        self.export_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; font-size: 14px;")
        self.export_btn.setEnabled(False) # Initially disabled
        self.export_btn.clicked.connect(self.export_results_to_excel)
        right_layout.addWidget(self.export_btn)
        
        self.status_label = QLabel("Ready") # The QLabel for status is still needed for BaseTab to set text/style
        right_layout.addWidget(self.status_label)
        
        self.job_status = JobStatusWidget("Discovery Job")
        right_layout.addWidget(self.job_status)

        # Linked Memories Section
        linked_memories_group = QGroupBox("Linked Memories")
        linked_memories_layout = QVBoxLayout(linked_memories_group)
        self.linked_memories_table = QTableWidget()
        self.linked_memories_table.setColumnCount(4)
        self.linked_memories_table.setHorizontalHeaderLabels(["Content", "Relation", "Source", "Linked At"])
        self.linked_memories_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        linked_memories_layout.addWidget(self.linked_memories_table)
        right_layout.addWidget(linked_memories_group)
        
        self.main_splitter.addWidget(right_widget)
        self.main_splitter.setSizes([450, 750])

    def on_kb_document_selected(self, doc):
        self.text_input.setPlainText(doc.get("content", ""))
        self.file_path.setText(doc.get("file_path", ""))
        self.status.success(f"Loaded: {doc.get('title')}")
        self.export_btn.setEnabled(False) # Disable export when new document is loaded
        self._refresh_action_state()
        # self.load_linked_memories() # Already connected via signal

    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Document", get_default_dialog_dir(), "All Files (*)")
        if path:
            self.file_path.setText(path)
            self.text_input.clear()
        self._refresh_action_state()
        # self.load_linked_memories() # Already connected via signal

    def _refresh_action_state(self) -> None:
        has_text = bool(self.text_input.toPlainText().strip())
        has_path = bool(self.file_path.text().strip())
        ready = has_text or has_path
        self.analyze_btn.setEnabled(ready)
        self.discover_btn_right.setEnabled(ready)
        if ready:
            self.prereq_status.setText("Ready: click Start Discovery.")
            self.prereq_status.setStyleSheet("color: #81c784; padding: 0 0 8px 0;")
        else:
            self.prereq_status.setText("Missing input: load a KB document, choose a file, or paste text.")
            self.prereq_status.setStyleSheet("color: #ffcc80; padding: 0 0 8px 0;")

    def analyze_document(self):
        text = self.text_input.toPlainText().strip()
        path = self.file_path.text().strip()
        if not text and not path:
            self.status.warn("Input required.")
            return

        self.job_status.set_status("running", "Clustering...")
        self.analyze_btn.setEnabled(False)
        self.status.loading("Identifying strategic themes...")
        self._refresh_action_state()

        options = {
            "auto_label": self.auto_label.isChecked(),
            "outliers": self.smoking_gun.isChecked()
        }

        worker_instance = SemanticAnalysisWorker(self.asyncio_thread, path, text, self.analysis_combo.currentText(), options)
        worker_instance.result_ready.connect(self.on_analysis_result)
        # BaseTab handles error_occurred and finished, so no need to connect directly
        self.start_worker(worker_instance)

    def export_results_to_excel(self):
        if not self.last_analysis_result or "semantic_analysis" not in self.last_analysis_result.get("data", {}):
            QMessageBox.warning(self, "Export Error", "No analysis results to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Results to Excel", get_default_dialog_dir(), "Excel Files (*.xlsx)"
        )

        if not file_path:
            return

        try:
            semantic_data = self.last_analysis_result["data"]["semantic_analysis"]

            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # 1. Summary
                summary_df = pd.DataFrame([{"Document Summary": semantic_data.get("document_summary", "N/A")}])
                summary_df.to_excel(writer, sheet_name="Summary", index=False)

                # 2. Key Topics
                key_topics = semantic_data.get("key_topics", [])
                if key_topics:
                    topics_data = []
                    for topic in key_topics:
                        topics_data.append({
                            "Topic Name": topic.get("topic_name", "N/A"),
                            "Category": topic.get("topic_category", "N/A"),
                            "Keywords": ", ".join(topic.get("keywords", [])),
                            "Confidence": topic.get("confidence", 0.0),
                            "Relevance Score": topic.get("relevance_score", 0.0),
                            "Legal Framework": topic.get("legal_framework", "N/A"),
                        })
                    topics_df = pd.DataFrame(topics_data)
                    topics_df.to_excel(writer, sheet_name="Key Topics", index=False)

                # 3. Legal Concepts
                legal_concepts = semantic_data.get("legal_concepts", [])
                if legal_concepts:
                    concepts_data = []
                    for concept in legal_concepts:
                        concepts_data.append({
                            "Concept": concept.get("concept", "N/A"),
                            "Type": concept.get("concept_type", "N/A"),
                            "Confidence": concept.get("confidence", 0.0),
                            "Context": concept.get("context", "N/A"),
                            "Legal Domain": concept.get("legal_domain", "N/A"),
                            "Relationships": ", ".join(concept.get("relationships", [])),
                            "Importance Score": concept.get("importance_score", 0.0),
                        })
                    concepts_df = pd.DataFrame(concepts_data)
                    concepts_df.to_excel(writer, sheet_name="Legal Concepts", index=False)

                # 4. Document Classification
                classification = semantic_data.get("document_classification", {})
                classification_df = pd.DataFrame([{
                    "Document Type": classification.get("document_type", "N/A"),
                    "Legal Domain": classification.get("legal_domain", "N/A"),
                    "Jurisdiction": classification.get("jurisdiction", "N/A"),
                    "Practice Area": classification.get("practice_area", "N/A"),
                    "Confidence": classification.get("confidence", 0.0),
                    "Classification Features": ", ".join(classification.get("classification_features", [])),
                }])
                classification_df.to_excel(writer, sheet_name="Classification", index=False)

                # 5. Semantic Relationships
                semantic_relationships = semantic_data.get("semantic_relationships", [])
                if semantic_relationships:
                    relationships_df = pd.DataFrame(semantic_relationships)
                    relationships_df.to_excel(writer, sheet_name="Relationships", index=False)
                
                # 6. Content Structure
                content_structure = semantic_data.get("content_structure", {})
                content_structure_data = [{
                    "Total Length": content_structure.get("total_length", "N/A"),
                    "Paragraph Count": content_structure.get("paragraph_count", "N/A"),
                    "Sentence Count": content_structure.get("sentence_count", "N/A"),
                    "Average Sentence Length": content_structure.get("avg_sentence_length", 0.0),
                    "Legal Sections": "; ".join([s.get('section', 'N/A') for s in content_structure.get('legal_sections', [])]),
                }]
                content_structure_df = pd.DataFrame(content_structure_data)
                content_structure_df.to_excel(writer, sheet_name="Content Structure", index=False)


            QMessageBox.information(self, "Export Successful", f"Results exported to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export results: {e}")

    async def load_linked_memories(self):
        """Loads and displays memories linked to the current file path."""
        file_path = self.file_path.text().strip()
        if not file_path:
            self.linked_memories_table.setRowCount(0)
            return

        self.status.loading(f"Loading linked memories for {file_path}...")
        try:
            # Use self.asyncio_thread to run the async API call
            linked_memories = await self.asyncio_thread.run_coroutine_threadsafe(
                api_client.get("/api/data-explorer/file-memories", params={"file_path": file_path})
            )
            self._display_linked_memories(linked_memories)
            self.status.success(f"Loaded {len(linked_memories)} linked memories.")
        except Exception as e:
            logger.error(f"Failed to load linked memories for {file_path}: {e}")
            self.status.error(f"Failed to load linked memories: {e}")
            self.linked_memories_table.setRowCount(0)

    def _display_linked_memories(self, memories: list[dict]):
        """Populates the linked memories table with data."""
        self.linked_memories_table.setRowCount(len(memories))
        for i, memory in enumerate(memories):
            self.linked_memories_table.setItem(i, 0, QTableWidgetItem(memory.get("content", "")))
            self.linked_memories_table.setItem(i, 1, QTableWidgetItem(memory.get("relation_type", "")))
            self.linked_memories_table.setItem(i, 2, QTableWidgetItem(memory.get("link_source", "")))
            self.linked_memories_table.setItem(i, 3, QTableWidgetItem(memory.get("linked_at", "").split("T")[0])) # Just date
