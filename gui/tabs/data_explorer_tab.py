"""
Data Explorer Tab - A unified interface for exploring project data.
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui.core.base_tab import BaseTab
from gui.services import api_client


class DataExplorerTab(BaseTab):
    """A tab for exploring unified project data."""

    def __init__(self, asyncio_thread: Optional[Any] = None, parent=None):
        super().__init__("Data Explorer", asyncio_thread, parent)
        self._clusters_payload: list[dict[str, Any]] = []
        self.setup_ui()

    def setup_ui(self) -> None:
        title = QLabel("Unified Data Explorer")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(title)

        query_layout = QHBoxLayout()
        self.query_input = QTextEdit()
        self.query_input.setPlaceholderText(
            "Ask about project data, e.g. 'show files' or 'show memories'."
        )
        self.query_input.setMaximumHeight(60)
        query_layout.addWidget(self.query_input)

        self.query_button = QPushButton("Ask")
        self.query_button.setMinimumHeight(60)
        self.query_button.clicked.connect(self._on_query_submitted)
        query_layout.addWidget(self.query_button)
        self.main_layout.addLayout(query_layout)

        self.results_tabs = QTabWidget()
        self.main_layout.addWidget(self.results_tabs)

        self._build_file_index_tab()
        self._build_unified_memory_tab()
        self._build_data_integrity_tab()
        self._build_code_hotspots_tab()
        self._build_memory_insights_tab()

        self.main_layout.addStretch()

    def _build_file_index_tab(self) -> None:
        self.file_index_tab = QWidget()
        layout = QVBoxLayout(self.file_index_tab)

        self.file_index_table = QTableWidget()
        self.file_index_table.setColumnCount(5)
        self.file_index_table.setHorizontalHeaderLabels(
            ["File Path", "Type", "Category", "Purpose", "Last Analyzed"]
        )
        self.file_index_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.file_index_table.itemSelectionChanged.connect(self._on_file_selection_changed)
        layout.addWidget(self.file_index_table)

        self.file_memory_label = QLabel("Associated Memories")
        self.file_memory_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.file_memory_label)

        self.file_memory_table = QTableWidget()
        self.file_memory_table.setColumnCount(8)
        self.file_memory_table.setHorizontalHeaderLabels(
            [
                "Record ID",
                "Key",
                "Memory Type",
                "Relation",
                "Link Confidence",
                "Source",
                "Linked At",
                "Content",
            ]
        )
        self.file_memory_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.file_memory_table)

        self.results_tabs.addTab(self.file_index_tab, "File Index")

    def _build_unified_memory_tab(self) -> None:
        self.unified_memory_tab = QWidget()
        layout = QVBoxLayout(self.unified_memory_tab)

        self.unified_memory_table = QTableWidget()
        self.unified_memory_table.setColumnCount(5)
        self.unified_memory_table.setHorizontalHeaderLabels(
            ["Namespace", "Key", "Content", "Type", "Agent"]
        )
        self.unified_memory_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.unified_memory_table)

        self.results_tabs.addTab(self.unified_memory_tab, "Unified Memory")

    def _build_data_integrity_tab(self) -> None:
        self.data_integrity_tab = QWidget()
        layout = QVBoxLayout(self.data_integrity_tab)

        header = QHBoxLayout()
        self.integrity_summary_label = QLabel("Integrity report not run yet.")
        header.addWidget(self.integrity_summary_label)
        self.run_integrity_button = QPushButton("Run Integrity Checks")
        self.run_integrity_button.clicked.connect(self._run_integrity_checks)
        header.addWidget(self.run_integrity_button)
        layout.addLayout(header)

        self.integrity_table = QTableWidget()
        self.integrity_table.setColumnCount(5)
        self.integrity_table.setHorizontalHeaderLabels(
            ["Check", "Severity", "Issue Count", "Details", "Recommended Action"]
        )
        self.integrity_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.integrity_table)

        self.results_tabs.addTab(self.data_integrity_tab, "Data Integrity")

    def _build_code_hotspots_tab(self) -> None:
        self.code_hotspots_tab = QWidget()
        layout = QVBoxLayout(self.code_hotspots_tab)

        header = QHBoxLayout()
        self.hotspot_summary_label = QLabel("Hotspot report not run yet.")
        header.addWidget(self.hotspot_summary_label)
        self.run_hotspots_button = QPushButton("Run Hotspot Analysis")
        self.run_hotspots_button.clicked.connect(self._run_hotspot_analysis)
        header.addWidget(self.run_hotspots_button)
        layout.addLayout(header)

        self.hotspots_table = QTableWidget()
        self.hotspots_table.setColumnCount(7)
        self.hotspots_table.setHorizontalHeaderLabels(
            [
                "File Path",
                "Hotspot Score",
                "Risk",
                "Change Events",
                "Issue Weight",
                "Complexity",
                "Recommended Action",
            ]
        )
        self.hotspots_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.hotspots_table)

        self.results_tabs.addTab(self.code_hotspots_tab, "Code Hotspots")

    def _build_memory_insights_tab(self) -> None:
        self.memory_insights_tab = QWidget()
        layout = QVBoxLayout(self.memory_insights_tab)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Cluster Count"))
        self.n_clusters_spinbox = QSpinBox()
        self.n_clusters_spinbox.setMinimum(2)
        self.n_clusters_spinbox.setMaximum(20)
        self.n_clusters_spinbox.setValue(5)
        controls.addWidget(self.n_clusters_spinbox)

        self.run_clustering_button = QPushButton("Run Clustering")
        self.run_clustering_button.clicked.connect(self._run_clustering)
        controls.addWidget(self.run_clustering_button)

        self.summarize_button = QPushButton("Summarize Selected Cluster")
        self.summarize_button.clicked.connect(self._summarize_selected_cluster)
        controls.addWidget(self.summarize_button)
        controls.addStretch()
        layout.addLayout(controls)

        self.clustered_memories_table = QTableWidget()
        self.clustered_memories_table.setColumnCount(5)
        self.clustered_memories_table.setHorizontalHeaderLabels(
            ["Cluster ID", "Size", "Memory Types", "Top Terms", "Summary"]
        )
        self.clustered_memories_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.clustered_memories_table)

        self.summary_text_edit = QTextEdit()
        self.summary_text_edit.setReadOnly(True)
        self.summary_text_edit.setPlaceholderText("Summary output will appear here.")
        layout.addWidget(self.summary_text_edit)

        self.results_tabs.addTab(self.memory_insights_tab, "Memory Insights")

    def _on_query_submitted(self) -> None:
        query = self.query_input.toPlainText().strip()
        if not query:
            QMessageBox.warning(self, "Warning", "Please enter a query.")
            return

        try:
            response = api_client.post("/data-explorer/query", {"query": query})
            self._handle_query_response(response)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to execute query: {exc}")

    def _handle_query_response(self, response: dict[str, Any]) -> None:
        source = response.get("source")
        data = response.get("data", [])

        if source == "file_index":
            self.results_tabs.setCurrentWidget(self.file_index_tab)
            self.file_index_table.setRowCount(len(data))
            for i, row in enumerate(data):
                self.file_index_table.setItem(i, 0, QTableWidgetItem(row.get("file_path", "")))
                self.file_index_table.setItem(i, 1, QTableWidgetItem(row.get("file_type", "")))
                self.file_index_table.setItem(i, 2, QTableWidgetItem(row.get("file_category", "")))
                self.file_index_table.setItem(
                    i, 3, QTableWidgetItem(row.get("primary_purpose", ""))
                )
                self.file_index_table.setItem(i, 4, QTableWidgetItem(row.get("last_analyzed", "")))
            return

        if source == "unified_memory":
            self.results_tabs.setCurrentWidget(self.unified_memory_tab)
            self.unified_memory_table.setRowCount(len(data))
            for i, row in enumerate(data):
                self.unified_memory_table.setItem(i, 0, QTableWidgetItem(row.get("namespace", "")))
                self.unified_memory_table.setItem(i, 1, QTableWidgetItem(row.get("key", "")))
                self.unified_memory_table.setItem(i, 2, QTableWidgetItem(row.get("content", "")))
                self.unified_memory_table.setItem(i, 3, QTableWidgetItem(row.get("memory_type", "")))
                self.unified_memory_table.setItem(i, 4, QTableWidgetItem(row.get("agent_id", "")))
            return

        QMessageBox.information(
            self,
            "Info",
            "The query did not return any results from known data sources.",
        )

    def _on_file_selection_changed(self) -> None:
        selected_items = self.file_index_table.selectedItems()
        if not selected_items:
            self.file_memory_table.setRowCount(0)
            return
        row = selected_items[0].row()
        file_item = self.file_index_table.item(row, 0)
        file_path = file_item.text().strip() if file_item else ""
        if not file_path:
            self.file_memory_table.setRowCount(0)
            return
        try:
            data = api_client.get(
                "/data-explorer/file-memories",
                params={"file_path": file_path, "limit": 100},
            )
            if not isinstance(data, list):
                data = []
            self.file_memory_table.setRowCount(len(data))
            for i, row_data in enumerate(data):
                self.file_memory_table.setItem(
                    i, 0, QTableWidgetItem(row_data.get("memory_record_id", ""))
                )
                self.file_memory_table.setItem(i, 1, QTableWidgetItem(row_data.get("key", "")))
                self.file_memory_table.setItem(
                    i, 2, QTableWidgetItem(row_data.get("memory_type", ""))
                )
                self.file_memory_table.setItem(
                    i, 3, QTableWidgetItem(row_data.get("relation_type", ""))
                )
                self.file_memory_table.setItem(
                    i, 4, QTableWidgetItem(str(row_data.get("link_confidence", "")))
                )
                self.file_memory_table.setItem(
                    i, 5, QTableWidgetItem(row_data.get("link_source", ""))
                )
                self.file_memory_table.setItem(
                    i, 6, QTableWidgetItem(row_data.get("linked_at", ""))
                )
                self.file_memory_table.setItem(i, 7, QTableWidgetItem(row_data.get("content", "")))
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load associated memories for selected file: {exc}",
            )

    def _run_integrity_checks(self) -> None:
        try:
            report = api_client.get("/data-explorer/integrity-report")
            issues = report.get("issues", [])
            self.integrity_summary_label.setText(
                "Status: "
                f"{report.get('status', 'unknown')} | "
                f"Checks: {report.get('total_checks', 0)} | "
                f"Issues: {report.get('total_issues', 0)} | "
                f"Highest Severity: {report.get('highest_severity', 'none')}"
            )
            self.integrity_table.setRowCount(len(issues))
            for i, issue in enumerate(issues):
                self.integrity_table.setItem(i, 0, QTableWidgetItem(str(issue.get("check_name", ""))))
                self.integrity_table.setItem(i, 1, QTableWidgetItem(str(issue.get("severity", ""))))
                self.integrity_table.setItem(i, 2, QTableWidgetItem(str(issue.get("issue_count", 0))))
                self.integrity_table.setItem(i, 3, QTableWidgetItem(str(issue.get("details", ""))))
                self.integrity_table.setItem(
                    i, 4, QTableWidgetItem(str(issue.get("recommended_action", "")))
                )
            self.results_tabs.setCurrentWidget(self.data_integrity_tab)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to run data integrity checks: {exc}")

    def _run_hotspot_analysis(self) -> None:
        try:
            rows = api_client.get("/data-explorer/hotspots", params={"limit": 100})
            if not isinstance(rows, list):
                rows = []
            self.hotspot_summary_label.setText(f"Hotspots analyzed: {len(rows)}")
            self.hotspots_table.setRowCount(len(rows))
            for i, row in enumerate(rows):
                self.hotspots_table.setItem(i, 0, QTableWidgetItem(str(row.get("file_path", ""))))
                self.hotspots_table.setItem(i, 1, QTableWidgetItem(str(row.get("hotspot_score", 0))))
                self.hotspots_table.setItem(i, 2, QTableWidgetItem(str(row.get("risk_level", ""))))
                self.hotspots_table.setItem(i, 3, QTableWidgetItem(str(row.get("change_events", 0))))
                self.hotspots_table.setItem(i, 4, QTableWidgetItem(str(row.get("issue_weight", 0))))
                self.hotspots_table.setItem(
                    i, 5, QTableWidgetItem(str(row.get("complexity_score", 0)))
                )
                self.hotspots_table.setItem(
                    i, 6, QTableWidgetItem(str(row.get("recommended_action", "")))
                )
            self.results_tabs.setCurrentWidget(self.code_hotspots_tab)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to run hotspot analysis: {exc}")

    def _run_clustering(self) -> None:
        try:
            clusters = api_client.get(
                "/data-explorer/memory-clusters",
                params={"n_clusters": self.n_clusters_spinbox.value(), "limit": 200},
            )
            if not isinstance(clusters, list):
                clusters = []
            self._clusters_payload = clusters
            self.clustered_memories_table.setRowCount(len(clusters))
            for i, cluster in enumerate(clusters):
                self.clustered_memories_table.setItem(
                    i, 0, QTableWidgetItem(str(cluster.get("cluster_id", "")))
                )
                self.clustered_memories_table.setItem(
                    i, 1, QTableWidgetItem(str(cluster.get("size", 0)))
                )
                self.clustered_memories_table.setItem(
                    i, 2, QTableWidgetItem(", ".join(cluster.get("memory_types", [])))
                )
                self.clustered_memories_table.setItem(
                    i, 3, QTableWidgetItem(", ".join(cluster.get("top_terms", [])))
                )
                self.clustered_memories_table.setItem(
                    i, 4, QTableWidgetItem(str(cluster.get("summary", "")))
                )
            self.results_tabs.setCurrentWidget(self.memory_insights_tab)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to run memory clustering: {exc}")

    def _summarize_selected_cluster(self) -> None:
        selected_rows = self.clustered_memories_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Warning", "Select one cluster to summarize.")
            return
        idx = selected_rows[0].row()
        if idx < 0 or idx >= len(self._clusters_payload):
            QMessageBox.warning(self, "Warning", "Selected cluster payload is unavailable.")
            return
        memory_ids = self._clusters_payload[idx].get("memory_ids", [])
        if not memory_ids:
            QMessageBox.warning(
                self, "Warning", "Selected cluster has no memory IDs to summarize."
            )
            return
        try:
            summary = api_client.post(
                "/data-explorer/memory-summaries",
                {
                    "memory_record_ids": memory_ids,
                    "summary_type": "concise",
                    "target_length": 180,
                },
            )
            self.summary_text_edit.setPlainText(summary.get("content", "No summary generated."))
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to summarize memories: {exc}")
