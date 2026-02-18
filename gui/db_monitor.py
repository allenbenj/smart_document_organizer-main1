#!/usr/bin/env python3
"""
Enhanced Real-Time Database Monitor GUI - Multi-Database Support
Supports code_database.db, file_tracker_new.db, project_status.db, comprehensive_project_status.db
"""

import sys
import sqlite3
import os
import platform
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QProgressBar,
    QTextEdit,
    QFrame,
    QPushButton,
    QGridLayout,
    QScrollArea,
    QComboBox,
    QGroupBox,
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont, QPalette, QColor

class StatCard(QFrame):
    """Styled stat card widget"""
    def __init__(self, title, value="0", color="#00ff88"):
        super().__init__()
        self.setFrameStyle(QFrame.Shape.Box)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #2a2a2a;
                border: 2px solid {color};
                border-radius: 8px;
                padding: 10px;
                margin: 5px;
            }}
        """)
        
        layout = QVBoxLayout()
        
        # Value label
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: bold;")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Title label
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #ccc; font-size: 12px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.value_label)
        layout.addWidget(title_label)
        self.setLayout(layout)
    
    def update_value(self, value):
        self.value_label.setText(str(value))

class DatabaseManager:
    """Manages multiple database connections and platform-specific paths"""
    
    def __init__(self):
        self.current_platform = platform.system()
        self.databases = self._initialize_database_paths()
        self.connection_status = {}
        self._test_all_connections()
    
    def _initialize_database_paths(self) -> Dict[str, str]:
        """Initialize database paths relative to project root"""
        base_dir = os.getcwd()
        # Create tools/data if it doesn't exist (for file_tracker)
        tools_data = os.path.join(base_dir, "tools", "data")
        os.makedirs(tools_data, exist_ok=True)
        
        return {
            "file_tracker": os.path.join(tools_data, "file_tracker_new.db"),
            "unified_memory": os.path.join(base_dir, "databases", "unified_memory.db"),
            "documents": os.path.join(base_dir, "mem_db", "data", "documents.db"),
            "memory_proposals": os.path.join(base_dir, "mem_db", "data", "memory_proposals.db")
        }
    
    def _test_all_connections(self):
        """Test connections to all databases"""
        for db_name, db_path in self.databases.items():
            self.connection_status[db_name] = self._test_connection(db_path)
    
    def _test_connection(self, db_path: str) -> Dict[str, Any]:
        """Test connection to a specific database"""
        status = {
            "connected": False,
            "path": db_path,
            "exists": False,
            "last_modified": None,
            "error": None
        }
        
        try:
            status["exists"] = os.path.exists(db_path)
            if status["exists"]:
                status["last_modified"] = datetime.fromtimestamp(os.path.getmtime(db_path))
                
                # Test actual connection
                conn = sqlite3.connect(db_path)
                conn.execute("SELECT 1")
                conn.close()
                status["connected"] = True
            else:
                status["error"] = "Database file does not exist"
                
        except Exception as e:
            status["error"] = str(e)
        
        return status
    
    def get_connection(self, db_name: str) -> Optional[sqlite3.Connection]:
        """Get database connection if available"""
        if db_name not in self.databases:
            return None
            
        if not self.connection_status[db_name]["connected"]:
            return None
            
        try:
            return sqlite3.connect(self.databases[db_name])
        except Exception:
            return None
    
    def refresh_connection_status(self):
        """Refresh connection status for all databases"""
        self._test_all_connections()
    
    def get_database_stats(self, db_name: str) -> Dict[str, Any]:
        """Get database-specific statistics"""
        conn = self.get_connection(db_name)
        if not conn:
            return {"error": "Database not accessible"}
        
        try:
            if db_name == "documents":
                return self._get_documents_stats(conn)
            elif db_name == "file_tracker":
                return self._get_file_tracker_stats(conn)
            elif db_name == "unified_memory":
                return self._get_unified_memory_stats(conn)
            elif db_name == "memory_proposals":
                return self._get_memory_proposals_stats(conn)
            else:
                return {"error": "Unknown database type"}
        except Exception as e:
            return {"error": str(e)}
        finally:
            conn.close()
    
    def _get_documents_stats(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        """Get statistics for documents.db"""
        cursor = conn.cursor()
        stats = {}
        
        try:
            # Files in index
            cursor.execute("SELECT COUNT(*) FROM files_index")
            stats["total_files"] = cursor.fetchone()[0]
            
            # Documents
            cursor.execute("SELECT COUNT(*) FROM documents")
            stats["total_documents"] = cursor.fetchone()[0]
            
            # Categories
            cursor.execute("SELECT category, COUNT(*) FROM documents GROUP BY category ORDER BY COUNT(*) DESC")
            stats["categories"] = cursor.fetchall()
            
            # Recent files
            cursor.execute("""
                SELECT display_name, status, file_size, last_checked_at
                FROM files_index 
                ORDER BY last_checked_at DESC 
                LIMIT 5
            """)
            stats["recent_files"] = cursor.fetchall()

            # Tasks
            cursor.execute("SELECT COUNT(*) FROM taskmaster_tasks")
            stats["total_tasks"] = cursor.fetchone()[0]
            
        except Exception as e:
            stats["error"] = str(e)
            
        return stats

    def _get_unified_memory_stats(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        """Get statistics for unified_memory.db"""
        cursor = conn.cursor()
        stats = {}
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [t[0] for t in cursor.fetchall()]
            stats["tables"] = tables
            
            table_counts = {}
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    table_counts[table] = cursor.fetchone()[0]
                except:
                    table_counts[table] = "N/A"
            stats["table_counts"] = table_counts
        except Exception as e:
            stats["error"] = str(e)
        return stats

    def _get_memory_proposals_stats(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        """Get statistics for memory_proposals.db"""
        cursor = conn.cursor()
        stats = {}
        try:
             # Organization Proposals
            cursor.execute("SELECT COUNT(*) FROM organization_proposals")
            stats["total_proposals"] = cursor.fetchone()[0]

            cursor.execute("""
                SELECT proposed_folder, COUNT(*) 
                FROM organization_proposals 
                GROUP BY proposed_folder 
                ORDER BY COUNT(*) DESC 
                LIMIT 5
            """)
            stats["folders"] = cursor.fetchall()
        except:
             # Fallback
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            stats["tables"] = [t[0] for t in cursor.fetchall()]
        return stats
    
    def _get_file_tracker_stats(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        """Get statistics for file_tracker_new.db"""
        cursor = conn.cursor()
        stats = {}
        
        # Total files
        cursor.execute("SELECT COUNT(*) FROM files")
        stats["total_files"] = cursor.fetchone()[0]
        
        # Analyzed files
        cursor.execute("SELECT COUNT(*) FROM file_analysis")
        stats["analyzed_files"] = cursor.fetchone()[0]
        
        # File types
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN file_path LIKE '%.md' THEN '.md'
                    WHEN file_path LIKE '%.json' THEN '.json'
                    WHEN file_path LIKE '%.js' THEN '.js'
                    WHEN file_path LIKE '%.py' THEN '.py'
                    WHEN file_path LIKE '%.txt' THEN '.txt'
                    ELSE 'other'
                END as ext,
                COUNT(*) as count
            FROM files 
            GROUP BY ext
            ORDER BY count DESC
        """)
        stats["file_types"] = cursor.fetchall()
        
        # Recent analysis
        cursor.execute("""
            SELECT file_name, primary_purpose, ai_model_used, analysis_timestamp
            FROM file_analysis 
            ORDER BY analysis_timestamp DESC 
            LIMIT 5
        """)
        stats["recent_files"] = cursor.fetchall()
        
        return stats
    
    def _get_project_status_stats(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        """Get statistics for project_status.db"""
        cursor = conn.cursor()
        stats = {}
        
        try:
            # Components
            cursor.execute("SELECT COUNT(*) FROM components")
            stats["total_components"] = cursor.fetchone()[0]
            
            # Phases
            cursor.execute("SELECT COUNT(*) FROM phases")
            stats["total_phases"] = cursor.fetchone()[0]
            
            # Tasks
            cursor.execute("SELECT COUNT(*) FROM tasks")
            stats["total_tasks"] = cursor.fetchone()[0]
            
            # Completion percentages
            cursor.execute("""
                SELECT c.name, AVG(t.completion_percentage) as avg_completion
                FROM components c
                LEFT JOIN tasks t ON c.component_id = t.component_id
                GROUP BY c.component_id, c.name
                ORDER BY avg_completion DESC
            """)
            stats["component_completion"] = cursor.fetchall()
            
        except sqlite3.OperationalError:
            # Fallback for unknown schema
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            stats["tables"] = [t[0] for t in tables]
            stats["error"] = "Schema unknown, showing table list"
        
        return stats
    
    def _get_comprehensive_status_stats(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        """Get statistics for comprehensive_project_status.db"""
        cursor = conn.cursor()
        stats = {}
        
        try:
            # Get table names first to understand schema
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [t[0] for t in cursor.fetchall()]
            stats["tables"] = tables
            
            # Try to get agent info if agents table exists
            if "agents" in tables:
                cursor.execute("SELECT COUNT(*) FROM agents")
                stats["total_agents"] = cursor.fetchone()[0]
            
            # Try to get model info if models table exists  
            if "models" in tables:
                cursor.execute("SELECT COUNT(*) FROM models")
                stats["total_models"] = cursor.fetchone()[0]
            
            # Get row counts for all tables
            table_counts = {}
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    table_counts[table] = cursor.fetchone()[0]
                except:
                    table_counts[table] = "N/A"
            
            stats["table_counts"] = table_counts
            
        except Exception as e:
            stats["error"] = str(e)
        
        return stats

class RealtimeDatabaseMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.db_manager = DatabaseManager()
        self.start_time = datetime.now()
        self.current_database = "file_tracker"  # Default database
        self.last_analyzed_count = 0
        
        # Dynamic stat cards that change based on database
        self.stat_cards = {}
        
        self.init_ui()
        self.setup_timer()
        self.update_database_display()
    
    def init_ui(self):
        self.setWindowTitle(" Enhanced AI Database Monitor - Multi-Database Support")
        self.setGeometry(100, 100, 1000, 800)
        
        # Enhanced dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a1a;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QTextEdit {
                background-color: #2a2a2a;
                border: 1px solid #444;
                border-radius: 5px;
                padding: 10px;
                color: #ffffff;
            }
            QPushButton {
                background-color: #00ff88;
                color: #000000;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00cc70;
            }
            QProgressBar {
                border: 2px solid #444;
                border-radius: 10px;
                background-color: #333;
                text-align: center;
                color: white;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                                          stop: 0 #00ff88, stop: 1 #00aa55);
                border-radius: 8px;
            }
            QComboBox {
                background-color: #333;
                border: 2px solid #555;
                border-radius: 5px;
                padding: 8px;
                color: white;
                font-size: 14px;
                min-width: 200px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 8px solid #00ff88;
                margin-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #333;
                border: 1px solid #555;
                selection-background-color: #00ff88;
                selection-color: black;
            }
            QGroupBox {
                border: 2px solid #555;
                border-radius: 8px;
                margin: 10px 0px;
                padding-top: 15px;
                font-weight: bold;
                font-size: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #00ff88;
            }
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Header
        header = QLabel(" Enhanced AI Database Monitor - Multi-Database Support")
        header.setStyleSheet("font-size: 22px; font-weight: bold; color: #00ff88; margin: 10px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Database selection and controls
        controls_layout = QHBoxLayout()
        
        # Database selector
        db_label = QLabel("Database:")
        db_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        controls_layout.addWidget(db_label)
        
        self.database_combo = QComboBox()
        self.database_combo.addItems([
            "file_tracker - File Analysis Tracker",
            "documents - Main Document/Code DB",
            "unified_memory - Agent Memory",
            "memory_proposals - Organization Proposals"
        ])
        self.database_combo.currentTextChanged.connect(self.on_database_changed)
        controls_layout.addWidget(self.database_combo)
        
        controls_layout.addStretch()
        
        # Refresh button
        refresh_btn = QPushButton(" Refresh All")
        refresh_btn.clicked.connect(self.refresh_all_connections)
        controls_layout.addWidget(refresh_btn)
        
        layout.addLayout(controls_layout)
        
        # Connection Status Section
        self.connection_group = QGroupBox(" Database Connection Status")
        connection_layout = QGridLayout(self.connection_group)
        
        self.connection_labels = {}
        for i, (db_name, _) in enumerate(self.db_manager.databases.items()):
            label = QLabel(f"{db_name}: Loading...")
            label.setStyleSheet("padding: 5px; font-family: monospace;")
            self.connection_labels[db_name] = label
            connection_layout.addWidget(label, i // 2, i % 2)
        
        layout.addWidget(self.connection_group)
        
        # Current Database Info
        self.current_db_label = QLabel("Current Database: Loading...")
        self.current_db_label.setStyleSheet("background-color: #333; padding: 10px; border-radius: 5px; margin: 10px 0; font-weight: bold;")
        layout.addWidget(self.current_db_label)
        
        # Dynamic Stats Section
        self.stats_group = QGroupBox(" Database Statistics")
        self.stats_layout = QGridLayout(self.stats_group)
        layout.addWidget(self.stats_group)
        
        # Progress bar (for applicable databases)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimumHeight(25)
        self.progress_bar.setVisible(False)  # Hidden by default, shown for relevant databases
        layout.addWidget(self.progress_bar)
        
        # API Stats (for file_tracker database)
        self.api_stats_group = QGroupBox(" API Usage Statistics")
        api_layout = QGridLayout(self.api_stats_group)
        
        self.api_calls_card = StatCard("API Calls", "0", "#9b59b6")
        self.tokens_card = StatCard("Tokens Used", "0", "#e67e22") 
        self.cost_card = StatCard("Est. Cost", "$0.00", "#2ecc71")
        self.runtime_card = StatCard("Runtime", "00:00", "#3498db")
        
        api_layout.addWidget(self.api_calls_card, 0, 0)
        api_layout.addWidget(self.tokens_card, 0, 1)
        api_layout.addWidget(self.cost_card, 0, 2)
        api_layout.addWidget(self.runtime_card, 0, 3)
        
        layout.addWidget(self.api_stats_group)
        
        # Recent Activity Section
        self.recent_group = QGroupBox(" Recent Activity")
        recent_layout = QVBoxLayout(self.recent_group)
        
        self.recent_files = QTextEdit()
        self.recent_files.setMaximumHeight(150)
        recent_layout.addWidget(self.recent_files)
        
        layout.addWidget(self.recent_group)
        
        # Details Section
        self.details_group = QGroupBox(" Detailed Information")
        details_layout = QVBoxLayout(self.details_group)
        
        self.details_text = QTextEdit()
        self.details_text.setMaximumHeight(120)
        details_layout.addWidget(self.details_text)
        
        layout.addWidget(self.details_group)
    
    def setup_timer(self):
        """Setup auto-refresh timer"""
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_database_display)
        self.timer.start(10000)  # Update every 10 seconds
    
    def on_database_changed(self):
        """Handle database selection change"""
        selected_text = self.database_combo.currentText()
        self.current_database = selected_text.split(" - ")[0]
        self.update_database_display()
    
    def refresh_all_connections(self):
        """Refresh all database connections"""
        self.db_manager.refresh_connection_status()
        self.update_connection_status()
        self.update_database_display()
    
    def update_connection_status(self):
        """Update connection status display"""
        for db_name, status in self.db_manager.connection_status.items():
            if status["connected"]:
                icon = ""
                color = "#00ff88"
                last_mod = status["last_modified"]
                mod_str = last_mod.strftime("%H:%M:%S") if last_mod else "Unknown"
                text = f"{icon} {db_name}: Connected (Modified: {mod_str})"
            elif status["exists"]:
                icon = ""
                color = "#ffaa00" 
                text = f"{icon} {db_name}: File exists but connection failed"
            else:
                icon = ""
                color = "#ff6b6b"
                text = f"{icon} {db_name}: File not found"
            
            self.connection_labels[db_name].setText(text)
            self.connection_labels[db_name].setStyleSheet(f"color: {color}; padding: 5px; font-family: monospace;")
    
    def clear_dynamic_stats(self):
        """Clear all dynamic stat cards"""
        for widget in self.stat_cards.values():
            widget.setParent(None)
        self.stat_cards.clear()
    
    def create_stat_cards_for_database(self, db_name: str):
        """Create stat cards specific to the database type"""
        self.clear_dynamic_stats()
        
        if db_name == "documents":
            self.stat_cards["files"] = StatCard("Indexed Files", "0", "#00ff88")
            self.stat_cards["docs"] = StatCard("Documents", "0", "#4ecdc4")
            self.stat_cards["tasks"] = StatCard("Tasks", "0", "#ffaa00")
            self.stat_cards["categories"] = StatCard("Categories", "0", "#9b59b6")
            
        elif db_name == "file_tracker":
            self.stat_cards["total"] = StatCard("Total Files", "0", "#00ff88")
            self.stat_cards["analyzed"] = StatCard("Analyzed", "0", "#ffaa00")
            self.stat_cards["progress"] = StatCard("Progress %", "0%", "#ff6b6b")
            self.stat_cards["types"] = StatCard("File Types", "0", "#4ecdc4")
            
        elif db_name == "unified_memory":
             self.stat_cards["tables"] = StatCard("Tables", "0", "#00ff88")
             self.stat_cards["records"] = StatCard("Total Records", "0", "#4ecdc4")
            
        elif db_name == "memory_proposals":
            self.stat_cards["proposals"] = StatCard("Proposals", "0", "#00ff88")
        
        # Add cards to layout
        row, col = 0, 0
        for card in self.stat_cards.values():
            self.stats_layout.addWidget(card, row, col)
            col += 1
            if col >= 4:
                col = 0
                row += 1
    
    def update_database_display(self):
        """Update display for currently selected database"""
        self.update_connection_status()
        
        # Update current database info
        db_path = self.db_manager.databases.get(self.current_database, "Unknown")
        platform = self.db_manager.current_platform
        status = self.db_manager.connection_status.get(self.current_database, {})
        
        status_icon = "" if status.get("connected") else ""
        self.current_db_label.setText(
            f"Current Database: {self.current_database} {status_icon} | "
            f"Platform: {platform} | Path: {db_path}"
        )
        
        # Create appropriate stat cards
        self.create_stat_cards_for_database(self.current_database)
        
        # Get and display database-specific stats
        stats = self.db_manager.get_database_stats(self.current_database)
        
        if "error" in stats:
            self.recent_files.setPlainText(f" Error: {stats['error']}")
            self.details_text.setPlainText("Database connection failed or data unavailable.")
            self.api_stats_group.setVisible(False)
            self.progress_bar.setVisible(False)
            return
        
        # Update stats based on database type
        if self.current_database == "documents":
            self.update_documents_display(stats)
        elif self.current_database == "file_tracker":
            self.update_file_tracker_display(stats)
        elif self.current_database == "unified_memory":
            self.update_unified_memory_display(stats)
        elif self.current_database == "memory_proposals":
            self.update_memory_proposals_display(stats)
        
        # Update runtime
        runtime = datetime.now() - self.start_time
        hours, remainder = divmod(runtime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        self.runtime_card.update_value(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
    
    def update_documents_display(self, stats):
        """Update display for documents.db"""
        self.api_stats_group.setVisible(False)
        self.progress_bar.setVisible(False)
        
        if "error" in stats:
            self.recent_files.setPlainText(f" Error: {stats['error']}")
            return

        # Update stat cards
        self.stat_cards["files"].update_value(f"{stats.get('total_files', 0):,}")
        self.stat_cards["docs"].update_value(f"{stats.get('total_documents', 0):,}")
        self.stat_cards["tasks"].update_value(f"{stats.get('total_tasks', 0):,}")
        
        categories = stats.get('categories', [])
        self.stat_cards["categories"].update_value(str(len(categories)))
        
        # Recent files
        recent_text = " Recently Indexed Files:\n\n"
        for name, status, size, timestamp in stats.get('recent_files', []):
            time_str = str(timestamp) if timestamp else "unknown"
            size_kb = size / 1024 if size else 0
            recent_text += f" {name}\n   Status: {status}, Size: {size_kb:.1f}KB - {time_str}\n\n"
        
        self.recent_files.setPlainText(recent_text)
        
        # Categories breakdown
        details_text = " Document Categories:\n\n"
        for cat, count in categories:
            details_text += f"{cat}: {count:,} documents\n"
        
        self.details_text.setPlainText(details_text)
    
    def update_file_tracker_display(self, stats):
        """Update display for file_tracker_new.db"""
        self.api_stats_group.setVisible(True)
        self.progress_bar.setVisible(True)
        
        total_files = stats.get('total_files', 0)
        analyzed_files = stats.get('analyzed_files', 0)
        
        # Update stat cards
        self.stat_cards["total"].update_value(f"{total_files:,}")
        self.stat_cards["analyzed"].update_value(f"{analyzed_files:,}")
        
        progress_pct = (analyzed_files / total_files * 100) if total_files > 0 else 0
        self.stat_cards["progress"].update_value(f"{progress_pct:.1f}%")
        self.progress_bar.setValue(int(progress_pct))
        
        self.stat_cards["types"].update_value(str(len(stats.get('file_types', []))))
        
        # API stats (try to get from log file)
        api_calls, tokens_used, cost = self.get_api_stats_from_log()
        self.api_calls_card.update_value(f"{api_calls:,}")
        self.tokens_card.update_value(f"{tokens_used:,}")
        self.cost_card.update_value(f"${cost:.4f}")
        
        # Recent files
        recent_text = " Recently Analyzed Files:\n\n"
        for file_name, purpose, model, timestamp in stats.get('recent_files', []):
            if timestamp:
                dt = datetime.fromtimestamp(timestamp)
                time_str = dt.strftime("%H:%M:%S")
            else:
                time_str = "recent"
            purpose_short = purpose[:60] + "..." if len(purpose) > 60 else purpose
            recent_text += f" {file_name}\n   {purpose_short} ({model}) - {time_str}\n\n"
        
        self.recent_files.setPlainText(recent_text)
        
        # File types
        details_text = " File Type Breakdown:\n\n"
        for ext, count in stats.get('file_types', []):
            details_text += f"{ext}: {count:,} files\n"
        
        self.details_text.setPlainText(details_text)
    
    def update_unified_memory_display(self, stats):
        """Update display for unified_memory.db"""
        self.api_stats_group.setVisible(False)
        self.progress_bar.setVisible(False)
        
        if "error" in stats:
            self.recent_files.setPlainText(f" Error: {stats['error']}")
            return
            
        tables = stats.get('tables', [])
        table_counts = stats.get('table_counts', {})
        
        self.stat_cards["tables"].update_value(str(len(tables)))
        
        total_records = 0
        for count in table_counts.values():
             if isinstance(count, int):
                 total_records += count
        self.stat_cards["records"].update_value(f"{total_records:,}")
        
        recent_text = " Database Tables:\n\n"
        for table in tables:
            count = table_counts.get(table, "N/A")
            recent_text += f" {table}: {count} records\n"
        
        self.recent_files.setPlainText(recent_text)
        self.details_text.setPlainText("Unified Memory Database - Agent Memory & Context")

    def update_memory_proposals_display(self, stats):
        """Update display for memory_proposals.db"""
        self.api_stats_group.setVisible(False)
        self.progress_bar.setVisible(False)

        if "error" in stats:
            self.recent_files.setPlainText(f" Error: {stats['error']}")
            return

        self.stat_cards["proposals"].update_value(f"{stats.get('total_proposals', 0):,}")

        recent_text = " Top Proposed Folders:\n\n"
        for folder, count in stats.get('folders', []):
            recent_text += f" {folder}: {count} proposals\n"
        self.recent_files.setPlainText(recent_text)
        self.details_text.setPlainText("Organization Proposals - Suggested file movements")
    
    def get_api_stats_from_log(self):
        """Get API statistics from log file"""
        api_calls = 0
        tokens_used = 0
        cost = 0.0
        
        # Determine log path based on platform
        if self.db_manager.current_platform == "Windows":
            log_path = r'E:\Coding_Project\bulk_analysis_monitor.log'
        else:
            log_path = '/mnt/e/Coding_Project/bulk_analysis_monitor.log'
        
        try:
            with open(log_path, 'r') as f:
                log_content = f.read()
                if " API Calls:" in log_content:
                    lines = log_content.split('\n')
                    for line in lines:
                        if " API Calls:" in line and "" in line:
                            api_calls = int(line.split('')[1].split()[0])
                        elif " Total Tokens:" in line:
                            tokens_used = int(line.split(':')[1].strip().replace(',', ''))
                        elif " Total Cost:" in line:
                            cost = float(line.split('$')[1].strip())
        except:
            pass
        
        return api_calls, tokens_used, cost

def main():
    app = QApplication(sys.argv)
    
    # Set dark theme
    app.setStyle('Fusion')
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(26, 26, 26))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Base, QColor(42, 42, 42))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(66, 66, 66))
    palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(palette)
    
    monitor = RealtimeDatabaseMonitor()
    monitor.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()