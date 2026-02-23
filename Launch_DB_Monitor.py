"""
Launch DB Monitor
=================
A professional GUI tool to monitor and inspect the project's SQLite databases.
"""

import sys
import os
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
        QLabel, QPushButton, QTabWidget, QStatusBar, QGroupBox,
        QLineEdit, QMessageBox, QSplitter, QFrame, QTextEdit,
        QAbstractItemView
    )
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QColor, QPalette, QFont, QAction
except ImportError:
    print("PySide6 is required. Please install it with: pip install PySide6")
    sys.exit(1)

# Professional Dark Theme
DARK_STYLESHEET = """
QMainWindow {
    background-color: #1e1e1e;
    color: #ffffff;
}
QWidget {
    background-color: #1e1e1e;
    color: #ffffff;
}
QGroupBox {
    border: 1px solid #3e3e3e;
    border-radius: 5px;
    margin-top: 10px;
    font-weight: bold;
    color: #4dabf7;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 3px;
}
QTableWidget {
    background-color: #252526;
    gridline-color: #3e3e3e;
    border: 1px solid #3e3e3e;
    color: #e0e0e0;
    selection-background-color: #264f78;
}
QHeaderView::section {
    background-color: #333333;
    color: #ffffff;
    padding: 4px;
    border: 1px solid #3e3e3e;
}
QTableWidget::item:selected {
    background-color: #264f78;
}
QLineEdit, QTextEdit {
    background-color: #252526;
    border: 1px solid #3e3e3e;
    color: #e0e0e0;
    padding: 4px;
    font-family: Consolas, monospace;
}
QPushButton {
    background-color: #0e639c;
    color: white;
    border: none;
    padding: 6px 12px;
    border-radius: 3px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #1177bb;
}
QPushButton:pressed {
    background-color: #094771;
}
QComboBox {
    background-color: #252526;
    border: 1px solid #3e3e3e;
    color: #e0e0e0;
    padding: 4px;
}
QComboBox::drop-down {
    border: none;
}
QStatusBar {
    background-color: #007acc;
    color: white;
}
QLabel#Heading {
    font-size: 16px;
    font-weight: bold;
    color: #4dabf7;
}
QLabel#StatLabel {
    color: #aaaaaa;
}
QLabel#StatValue {
    font-weight: bold;
    color: #ffffff;
    font-size: 14px;
}
"""

class DBMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart Document Organizer - DB Monitor")
        self.resize(1200, 800)
        
        # Database Configuration
        self.db_config = [
            {
                "name": "Documents DB",
                "path": Path("mem_db/data/documents.db"),
                "description": "Core document storage and metadata"
            },
            {
                "name": "Unified Memory",
                "path": Path("databases/unified_memory.db"),
                "description": "Agent shared memory and vector references"
            },
            {
                "name": "Memory Proposals",
                "path": Path("mem_db/data/memory_proposals.db"),
                "description": "Pending and approved memory proposals"
            },
            {
                "name": "File Index",
                "path": Path("databases/file_index.db"),
                "description": "File system index and tracking"
            }
        ]
        
        self.current_conn = None
        self.setup_ui()
        self.apply_styles()
        
        # Load initial DB
        QTimer.singleShot(100, self.load_initial_db)

    def apply_styles(self):
        self.setStyleSheet(DARK_STYLESHEET)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- Top Bar ---
        top_bar = QHBoxLayout()
        
        # DB Selector
        top_bar.addWidget(QLabel("Database:"))
        self.db_selector = QComboBox()
        for db in self.db_config:
            self.db_selector.addItem(f"{db['name']} ({db['path'].name})", db)
        self.db_selector.currentIndexChanged.connect(self.on_db_changed)
        self.db_selector.setMinimumWidth(250)
        top_bar.addWidget(self.db_selector)
        
        # Refresh Button
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.refresh_current_view)
        top_bar.addWidget(self.refresh_btn)
        
        top_bar.addStretch()
        
        # Status Indicator
        self.connection_status = QLabel("Disconnected")
        self.connection_status.setStyleSheet("color: #f44336; font-weight: bold;")
        top_bar.addWidget(self.connection_status)
        
        main_layout.addLayout(top_bar)

        # --- Main Content Area ---
        self.tabs = QTabWidget()
        
        # Tab 1: Overview
        self.overview_tab = QWidget()
        self.setup_overview_tab()
        self.tabs.addTab(self.overview_tab, "📊 Overview")
        
        # Tab 2: Data Inspector
        self.data_tab = QWidget()
        self.setup_data_tab()
        self.tabs.addTab(self.data_tab, "📋 Data Inspector")
        
        # Tab 3: SQL Query
        self.query_tab = QWidget()
        self.setup_query_tab()
        self.tabs.addTab(self.query_tab, "💻 SQL Query")
        
        main_layout.addWidget(self.tabs)

        # --- Status Bar ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def setup_overview_tab(self):
        layout = QVBoxLayout(self.overview_tab)
        
        # Info Box
        self.info_group = QGroupBox("Database Information")
        info_layout = QVBoxLayout(self.info_group)
        self.db_path_label = QLabel("Path: -")
        self.db_size_label = QLabel("Size: -")
        info_layout.addWidget(self.db_path_label)
        info_layout.addWidget(self.db_size_label)
        layout.addWidget(self.info_group)
        
        # Stats Box
        stats_group = QGroupBox("Statistics")
        self.stats_layout = QHBoxLayout(stats_group)
        layout.addWidget(stats_group)
        
        # Tables List
        tables_group = QGroupBox("Tables")
        tables_layout = QVBoxLayout(tables_group)
        self.tables_list = QTableWidget()
        self.tables_list.setColumnCount(3)
        self.tables_list.setHorizontalHeaderLabels(["Table Name", "Row Count", "Columns"])
        self.tables_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tables_list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tables_list.itemDoubleClicked.connect(self.on_table_double_clicked)
        tables_layout.addWidget(self.tables_list)
        layout.addWidget(tables_group)

    def setup_data_tab(self):
        layout = QVBoxLayout(self.data_tab)
        
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Table:"))
        self.table_selector = QComboBox()
        self.table_selector.currentTextChanged.connect(self.load_table_data)
        controls.addWidget(self.table_selector)
        
        controls.addWidget(QLabel("Limit:"))
        self.limit_selector = QComboBox()
        self.limit_selector.addItems(["100", "500", "1000", "5000"])
        self.limit_selector.currentTextChanged.connect(self.load_table_data)
        controls.addWidget(self.limit_selector)
        
        controls.addStretch()
        layout.addLayout(controls)
        
        self.data_table = QTableWidget()
        self.data_table.setAlternatingRowColors(True)
        layout.addWidget(self.data_table)

    def setup_query_tab(self):
        layout = QVBoxLayout(self.query_tab)
        
        self.query_editor = QTextEdit()
        self.query_editor.setPlaceholderText("SELECT * FROM ...")
        self.query_editor.setMaximumHeight(150)
        layout.addWidget(self.query_editor)
        
        btn_row = QHBoxLayout()
        run_btn = QPushButton("▶ Run Query")
        run_btn.clicked.connect(self.run_custom_query)
        btn_row.addWidget(run_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        
        self.query_results = QTableWidget()
        layout.addWidget(self.query_results)

    def load_initial_db(self):
        if self.db_config:
            self.connect_to_db(self.db_config[0])

    def on_db_changed(self, index):
        db_info = self.db_selector.itemData(index)
        self.connect_to_db(db_info)

    def connect_to_db(self, db_info):
        if self.current_conn:
            self.current_conn.close()
        
        path = db_info["path"]
        if not path.exists():
            self.connection_status.setText("Not Found")
            self.connection_status.setStyleSheet("color: #f44336; font-weight: bold;")
            self.status_bar.showMessage(f"Database file not found: {path}")
            self.clear_ui()
            return

        try:
            self.current_conn = sqlite3.connect(str(path))
            self.connection_status.setText("Connected")
            self.connection_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.status_bar.showMessage(f"Connected to {db_info['name']}")
            self.refresh_current_view()
        except Exception as e:
            self.connection_status.setText("Error")
            self.status_bar.showMessage(f"Connection error: {e}")

    def refresh_current_view(self):
        if not self.current_conn:
            return
            
        self.update_overview()
        self.update_table_list()
        
        # Refresh data tab if visible
        if self.tabs.currentIndex() == 1:
            self.load_table_data()

    def update_overview(self):
        db_info = self.db_selector.currentData()
        path = db_info["path"]
        
        # Update Info
        self.db_path_label.setText(f"Path: {path.absolute()}")
        size_mb = path.stat().st_size / (1024 * 1024)
        self.db_size_label.setText(f"Size: {size_mb:.2f} MB")
        
        # Clear stats layout
        while self.stats_layout.count():
            child = self.stats_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        # Get Table Count
        cursor = self.current_conn.cursor()
        cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
        table_count = cursor.fetchone()[0]
        
        self.add_stat_widget("Tables", str(table_count))
        self.add_stat_widget("Last Modified", datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M"))

    def add_stat_widget(self, label, value):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label)
        lbl.setObjectName("StatLabel")
        val = QLabel(value)
        val.setObjectName("StatValue")
        layout.addWidget(lbl)
        layout.addWidget(val)
        self.stats_layout.addWidget(widget)

    def update_table_list(self):
        cursor = self.current_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        self.tables_list.setRowCount(len(tables))
        self.table_selector.blockSignals(True)
        self.table_selector.clear()
        self.table_selector.addItems(tables)
        self.table_selector.blockSignals(False)
        
        for i, table in enumerate(tables):
            # Row count
            try:
                cursor.execute(f"SELECT count(*) FROM {table}")
                count = cursor.fetchone()[0]
            except:
                count = "?"
                
            # Column count
            try:
                cursor.execute(f"PRAGMA table_info({table})")
                cols = len(cursor.fetchall())
            except:
                cols = "?"
                
            self.tables_list.setItem(i, 0, QTableWidgetItem(table))
            self.tables_list.setItem(i, 1, QTableWidgetItem(str(count)))
            self.tables_list.setItem(i, 2, QTableWidgetItem(str(cols)))

    def on_table_double_clicked(self, item):
        row = item.row()
        table_name = self.tables_list.item(row, 0).text()
        self.table_selector.setCurrentText(table_name)
        self.tabs.setCurrentIndex(1) # Switch to Data Inspector

    def load_table_data(self):
        if not self.current_conn:
            return
            
        table = self.table_selector.currentText()
        if not table:
            return
            
        limit = self.limit_selector.currentText()
        
        try:
            cursor = self.current_conn.cursor()
            cursor.execute(f"SELECT * FROM {table} LIMIT {limit}")
            rows = cursor.fetchall()
            
            # Get headers
            cursor.execute(f"PRAGMA table_info({table})")
            headers = [col[1] for col in cursor.fetchall()]
            
            self.populate_table_widget(self.data_table, headers, rows)
            self.status_bar.showMessage(f"Loaded {len(rows)} rows from {table}")
        except Exception as e:
            self.status_bar.showMessage(f"Error loading data: {e}")

    def run_custom_query(self):
        if not self.current_conn:
            return
            
        query = self.query_editor.toPlainText().strip()
        if not query:
            return
            
        try:
            cursor = self.current_conn.cursor()
            cursor.execute(query)
            
            if query.lower().startswith("select") or query.lower().startswith("pragma"):
                rows = cursor.fetchall()
                headers = [description[0] for description in cursor.description] if cursor.description else []
                self.populate_table_widget(self.query_results, headers, rows)
                self.status_bar.showMessage(f"Query returned {len(rows)} rows")
            else:
                self.current_conn.commit()
                self.status_bar.showMessage(f"Query executed successfully. Rows affected: {cursor.rowcount}")
                self.refresh_current_view()
                
        except Exception as e:
            QMessageBox.critical(self, "Query Error", str(e))

    def populate_table_widget(self, widget, headers, rows):
        widget.clear()
        widget.setColumnCount(len(headers))
        widget.setHorizontalHeaderLabels(headers)
        widget.setRowCount(len(rows))
        
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                item = QTableWidgetItem(str(val) if val is not None else "NULL")
                widget.setItem(i, j, item)

    def clear_ui(self):
        self.db_path_label.setText("Path: -")
        self.db_size_label.setText("Size: -")
        self.tables_list.setRowCount(0)
        self.data_table.setRowCount(0)
        self.query_results.setRowCount(0)

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = DBMonitor()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()