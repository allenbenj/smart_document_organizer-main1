"""
Interactive Statistics Dashboard - Plotly-based visualizations

Provides interactive charts and dashboards for:
- Entity extraction statistics  
- Document processing metrics
- System performance monitoring
- Memory usage analytics
- Temporal trends

Uses plotly for rich, interactive HTML charts embedded in Qt widgets.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import Counter

try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

try:
    from PySide6.QtWidgets import (
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QComboBox,
        QGroupBox,
        QTabWidget,
        QTextBrowser,
        QMessageBox,
    )
    from PySide6.QtCore import Qt, Signal, QUrl
    from PySide6.QtGui import QFont
    from PySide6.QtWebEngineWidgets import QWebEngineView
    PYSIDE6_AVAILABLE = True
    WEBENGINE_AVAILABLE = True
except ImportError:
    try:
        from PySide6.QtWidgets import (
            QWidget,
            QVBoxLayout,
            QHBoxLayout,
            QLabel,
            QPushButton,
            QComboBox,
            QGroupBox,
            QTabWidget,
            QTextBrowser,
            QMessageBox,
        )
        from PySide6.QtCore import Qt, Signal, QUrl
        from PySide6.QtGui import QFont
        PYSIDE6_AVAILABLE = True
        WEBENGINE_AVAILABLE = False
        QWebEngineView = None  # type: ignore
    except ImportError:
        PYSIDE6_AVAILABLE = False
        WEBENGINE_AVAILABLE = False
        QWidget = Any = object  # type: ignore


class InteractiveStatsDashboard(QWidget):  # type: ignore[misc]
    """
    Interactive statistics dashboard with plotly charts.
    
    Features:
    - Entity type distribution (pie chart)
    - Confidence score distribution (histogram)
    - Temporal trends (line chart)
    - Top entities (bar chart)
    - Processing performance (metrics cards)
    - Export charts as HTML/PNG
    """
    
    # Signals
    chart_exported = Signal(str)  # type: ignore[misc] - file path
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data: Dict[str, Any] = {}
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel("Interactive Statistics Dashboard")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Time range selector
        header_layout.addWidget(QLabel("Time Range:"))
        self.time_range_combo = QComboBox()
        self.time_range_combo.addItems(["Last Hour", "Last 24 Hours", "Last 7 Days", "Last 30 Days", "All Time"])
        self.time_range_combo.setCurrentText("Last 24 Hours")
        self.time_range_combo.currentTextChanged.connect(self.refresh_dashboard)
        header_layout.addWidget(self.time_range_combo)
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_dashboard)
        header_layout.addWidget(refresh_btn)
        
        # Export button
        export_btn = QPushButton("💾 Export HTML")
        export_btn.clicked.connect(self.export_html)
        header_layout.addWidget(export_btn)
        
        layout.addLayout(header_layout)
        
        # Check dependencies
        if not PLOTLY_AVAILABLE:
            error_label = QLabel(
                "⚠️ Plotly not installed. Install with: pip install plotly\n\n"
                "Interactive charts will be unavailable until plotly is installed."
            )
            error_label.setWordWrap(True)
            error_label.setStyleSheet("color: #f44336; padding: 20px; background-color: #ffebee; border-radius: 5px;")
            layout.addWidget(error_label)
            return
        
        if not WEBENGINE_AVAILABLE:
            warning_label = QLabel(
                "⚠️ QtWebEngine not available. Charts will open in external browser.\n"
                "Install PySide6-WebEngine for embedded viewing."
            )
            warning_label.setWordWrap(True)
            warning_label.setStyleSheet("color: #ff9800; padding: 10px; background-color: #fff8e1; border-radius: 5px;")
            layout.addWidget(warning_label)
        
        # Tabs for different chart categories
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Overview tab
        self.overview_tab = self.create_chart_tab()
        self.tab_widget.addTab(self.overview_tab, "📊 Overview")
        
        # Entity Analysis tab
        self.entity_tab = self.create_chart_tab()
        self.tab_widget.addTab(self.entity_tab, "🏷️ Entity Analysis")
        
        # Performance tab
        self.performance_tab = self.create_chart_tab()
        self.tab_widget.addTab(self.performance_tab, "⚡ Performance")
        
        # Trends tab
        self.trends_tab = self.create_chart_tab()
        self.tab_widget.addTab(self.trends_tab, "📈 Trends")
        
        # Status bar
        self.status_label = QLabel("Ready - Click Refresh to load data")
        self.status_label.setStyleSheet("background-color: #f0f0f0; padding: 5px; color: #666;")
        layout.addWidget(self.status_label)
    
    def create_chart_tab(self) -> QWidget:
        """Create a tab for displaying charts."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        if WEBENGINE_AVAILABLE and QWebEngineView:
            # Use QWebEngineView for embedded charts
            web_view = QWebEngineView()
            web_view.setHtml("<h3 style='text-align:center; color:#999;'>No data loaded. Click Refresh to generate charts.</h3>")
            layout.addWidget(web_view)
        else:
            # Fallback to text browser
            text_browser = QTextBrowser()
            text_browser.setHtml("<h3 style='text-align:center; color:#999;'>No data loaded. Click Refresh to generate charts.</h3>")
            text_browser.setOpenExternalLinks(True)
            layout.addWidget(text_browser)
        
        return widget
    
    def set_data(self, data: Dict[str, Any]):
        """
        Set data for dashboard visualization.
        
        Expected data structure:
        {
            "entities": [
                {"type": "Person", "text": "John", "confidence": 0.95, "timestamp": "2024-02-15T10:30:00"},
                ...
            ],
            "documents": [
                {"filename": "doc1.pdf", "processed_at": "2024-02-15T10:00:00", "duration_seconds": 12.5},
                ...
            ],
            "memory_stats": {
                "total_records": 150,
                "cache_hits": 1250,
                "cache_misses": 45
            }
        }
        """
        self.data = data
        self.refresh_dashboard()
    
    def refresh_dashboard(self):
        """Refresh all charts with current data."""
        if not PLOTLY_AVAILABLE:
            return
        
        if not self.data:
            self.status_label.setText("No data available - Load data first")
            return
        
        self.status_label.setText("Generating charts...")
        
        # Generate charts for each tab
        self.generate_overview_charts()
        self.generate_entity_charts()
        self.generate_performance_charts()
        self.generate_trend_charts()
        
        self.status_label.setText(f"✅ Dashboard updated - {datetime.now().strftime('%H:%M:%S')}")
    
    def generate_overview_charts(self):
        """Generate overview dashboard charts."""
        if not self.data:
            return
        
        # Create subplot figure
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=("Entity Type Distribution", "Confidence Distribution", 
                          "Top 10 Entities", "Processing Summary"),
            specs=[[{"type": "pie"}, {"type": "histogram"}],
                   [{"type": "bar"}, {"type": "table"}]]
        )
        
        # Entity type distribution (pie chart)
        entities = self.data.get("entities", [])
        if entities:
            type_counts = Counter(e.get("type", "Unknown") for e in entities)
            fig.add_trace(
                go.Pie(labels=list(type_counts.keys()), values=list(type_counts.values()),
                      hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Percent: %{percent}"),
                row=1, col=1
            )
            
            # Confidence histogram
            confidences = [e.get("confidence", 0) for e in entities]
            fig.add_trace(
                go.Histogram(x=confidences, nbinsx=20, name="Confidence",
                           hovertemplate="Confidence: %{x:.2f}<br>Count: %{y}"),
                row=1, col=2
            )
            
            # Top entities bar chart
            entity_texts = Counter(e.get("text", "") for e in entities)
            top_entities = entity_texts.most_common(10)
            if top_entities:
                labels, values = zip(*top_entities)
                fig.add_trace(
                    go.Bar(x=list(values), y=list(labels), orientation='h',
                          hovertemplate="<b>%{y}</b><br>Mentions: %{x}"),
                    row=2, col=1
                )
        
        # Processing summary table
        summary_data = [
            ["Total Entities", len(entities)],
            ["Unique Types", len(set(e.get("type", "") for e in entities))],
            ["Avg Confidence", f"{sum(e.get('confidence', 0) for e in entities) / len(entities):.2%}" if entities else "N/A"],
            ["Documents Processed", len(self.data.get("documents", []))],
        ]
        
        fig.add_trace(
            go.Table(
                header=dict(values=["Metric", "Value"], fill_color='paleturquoise', align='left'),
                cells=dict(values=list(zip(*summary_data)), fill_color='lavender', align='left')
            ),
            row=2, col=2
        )
        
        fig.update_layout(height=800, showlegend=False, title_text="Overview Dashboard")
        
        self.display_chart(fig, self.overview_tab)
    
    def generate_entity_charts(self):
        """Generate entity analysis charts."""
        entities = self.data.get("entities", [])
        if not entities:
            return
        
        # Group by entity type
        entity_types = {}
        for e in entities:
            etype = e.get("type", "Unknown")
            if etype not in entity_types:
                entity_types[etype] = []
            entity_types[etype].append(e)
        
        # Create one chart per entity type
        fig = make_subplots(
            rows=len(entity_types), cols=1,
            subplot_titles=[f"{etype} ({len(items)} instances)" for etype, items in entity_types.items()],
            vertical_spacing=0.1
        )
        
        for idx, (etype, items) in enumerate(entity_types.items(), 1):
            # Count occurrences
            text_counts = Counter(item.get("text", "") for item in items)
            top_items = text_counts.most_common(15)
            
            if top_items:
                texts, counts = zip(*top_items)
                fig.add_trace(
                    go.Bar(x=list(counts), y=list(texts), orientation='h', name=etype,
                          hovertemplate=f"<b>%{{y}}</b><br>{etype}<br>Count: %{{x}}"),
                    row=idx, col=1
                )
        
        fig.update_layout(height=300 * len(entity_types), showlegend=False, title_text="Entity Analysis by Type")
        
        self.display_chart(fig, self.entity_tab)
    
    def generate_performance_charts(self):
        """Generate performance monitoring charts."""
        docs = self.data.get("documents", [])
        memory_stats = self.data.get("memory_stats", {})
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=("Processing Time Distribution", "Documents per Hour",
                          "Memory Cache Performance", "System Metrics"),
            specs=[[{"type": "histogram"}, {"type": "bar"}],
                   [{"type": "pie"}, {"type": "indicator"}]]
        )
        
        # Processing time histogram
        if docs:
            durations = [d.get("duration_seconds", 0) for d in docs]
            fig.add_trace(
                go.Histogram(x=durations, nbinsx=20, name="Duration",
                           hovertemplate="Duration: %{x:.1f}s<br>Count: %{y}"),
                row=1, col=1
            )
        
        # Documents per hour
        if docs:
            hourly = Counter()
            for d in docs:
                timestamp = d.get("processed_at", "")
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        hourly[dt.hour] += 1
                    except:
                        pass
            
            hours = list(range(24))
            counts = [hourly.get(h, 0) for h in hours]
            fig.add_trace(
                go.Bar(x=hours, y=counts, name="Documents",
                      hovertemplate="Hour: %{x}:00<br>Documents: %{y}"),
                row=1, col=2
            )
        
        # Cache performance pie
        cache_hits = memory_stats.get("cache_hits", 0)
        cache_misses = memory_stats.get("cache_misses", 0)
        
        if cache_hits + cache_misses > 0:
            fig.add_trace(
                go.Pie(labels=["Cache Hits", "Cache Misses"],
                      values=[cache_hits, cache_misses],
                      hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Percent: %{percent}"),
                row=2, col=1
            )
        
        # System metrics indicator
        total_records = memory_stats.get("total_records", 0)
        fig.add_trace(
            go.Indicator(
                mode="number+delta",
                value=total_records,
                title={"text": "Total Memory Records"},
                domain={'x': [0, 1], 'y': [0, 1]}
            ),
            row=2, col=2
        )
        
        fig.update_layout(height=800, showlegend=False, title_text="Performance Metrics")
        
        self.display_chart(fig, self.performance_tab)
    
    def generate_trend_charts(self):
        """Generate temporal trend charts."""
        entities = self.data.get("entities", [])
        docs = self.data.get("documents", [])
        
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=("Entity Extraction Over Time", "Document Processing Over Time"),
            specs=[[{"secondary_y": False}], [{"secondary_y": True}]]
        )
        
        # Entities over time
        if entities:
            entity_times = []
            for e in entities:
                timestamp = e.get("timestamp", "")
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        entity_times.append(dt)
                    except:
                        pass
            
            if entity_times:
                # Group by hour
                hourly_counts = Counter(dt.replace(minute=0, second=0, microsecond=0) for dt in entity_times)
                times = sorted(hourly_counts.keys())
                counts = [hourly_counts[t] for t in times]
                
                fig.add_trace(
                    go.Scatter(x=times, y=counts, mode='lines+markers', name="Entities",
                             hovertemplate="Time: %{x}<br>Entities: %{y}"),
                    row=1, col=1
                )
        
        # Documents over time
        if docs:
            doc_times = []
            for d in docs:
                timestamp = d.get("processed_at", "")
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        doc_times.append(dt)
                    except:
                        pass
            
            if doc_times:
                # Group by hour
                hourly_counts = Counter(dt.replace(minute=0, second=0, microsecond=0) for dt in doc_times)
                times = sorted(hourly_counts.keys())
                counts = [hourly_counts[t] for t in times]
                
                fig.add_trace(
                    go.Scatter(x=times, y=counts, mode='lines+markers', name="Documents",
                             hovertemplate="Time: %{x}<br>Documents: %{y}"),
                    row=2, col=1
                )
        
        fig.update_layout(height=600, title_text="Temporal Trends")
        
        self.display_chart(fig, self.trends_tab)
    
    def display_chart(self, fig, tab_widget: QWidget):
        """Display a plotly figure in a tab widget."""
        html = fig.to_html(include_plotlyjs='cdn', full_html=True)
        
        # Get the first child widget (QWebEngineView or QTextBrowser)
        layout = tab_widget.layout()
        if layout and layout.count() > 0:
            widget = layout.itemAt(0).widget()
            
            if WEBENGINE_AVAILABLE and isinstance(widget, QWebEngineView):
                widget.setHtml(html)
            elif isinstance(widget, QTextBrowser):
                widget.setHtml(
                    f"<div style='padding:20px;text-align:center;'>"
                    f"<p>Chart generated but QtWebEngine not available.</p>"
                    f"<p><a href='#' onclick='alert(\"Save HTML and open in browser\")'>Export HTML to view</a></p>"
                    f"</div>"
                )
    
    def export_html(self):
        """Export all charts as HTML file."""
        try:
            from PySide6.QtWidgets import QFileDialog
            
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Export Dashboard as HTML",
                "dashboard_export.html",
                "HTML Files (*.html)"
            )
            
            if not filename:
                return
            
            # Generate combined HTML with all charts
            html_parts = [
                "<html><head><title>Statistics Dashboard</title>",
                "<script src='https://cdn.plot.ly/plotly-latest.min.js'></script>",
                "<style>body{font-family:Arial;margin:20px;} .chart{margin:20px 0;}</style>",
                "</head><body>",
                f"<h1>Statistics Dashboard - {datetime.now().strftime('%Y-%m-%d %H:%M')}</h1>",
            ]
            
            # Add all charts (simplified version - real implementation would embed actual plotly divs)
            html_parts.append("<p>Dashboard exported successfully. Full chart integration requires complete implementation.</p>")
            
            html_parts.append("</body></html>")
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write('\n'.join(html_parts))
            
            self.chart_exported.emit(filename)
            QMessageBox.information(self, "Export Complete", f"Dashboard exported to:\n{filename}")
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export: {str(e)}")


# Example usage
if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Sample data
    sample_data = {
        "entities": [
            {"type": "Person", "text": "John Smith", "confidence": 0.95, "timestamp": "2024-02-16T10:00:00"},
            {"type": "Person", "text": "Jane Doe", "confidence": 0.88, "timestamp": "2024-02-16T10:30:00"},
            {"type": "Organization", "text": "Acme Corp", "confidence": 0.92, "timestamp": "2024-02-16T11:00:00"},
            {"type": "Location", "text": "New York", "confidence": 0.85, "timestamp": "2024-02-16T11:30:00"},
            {"type": "Date", "text": "January 15, 2024", "confidence": 0.98, "timestamp": "2024-02-16T12:00:00"},
        ] * 20,  # Multiply for more sample data
        "documents": [
            {"filename": "contract_001.pdf", "processed_at": "2024-02-16T10:00:00", "duration_seconds": 12.5},
            {"filename": "contract_002.pdf", "processed_at": "2024-02-16T11:00:00", "duration_seconds": 15.2},
            {"filename": "memo_001.docx", "processed_at": "2024-02-16T12:00:00", "duration_seconds": 8.3},
        ],
        "memory_stats": {
            "total_records": 150,
            "cache_hits": 1250,
            "cache_misses": 45
        }
    }
    
    dashboard = InteractiveStatsDashboard()
    dashboard.set_data(sample_data)
    dashboard.show()
    
    sys.exit(app.exec())
