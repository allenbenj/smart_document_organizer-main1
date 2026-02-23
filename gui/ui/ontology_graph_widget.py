"""
Ontology Graph Visualization Widget

Provides interactive visualization of entity relationships and ontology structure
using NetworkX for graph building and Plotly for 3D/2D interactive rendering.

Features:
- Entity relationship graph with nodes and edges
- Color-coded by entity type
- Interactive: zoom, pan, click nodes for details
- Filter by entity type, relationship type
- 3D and 2D visualization modes
- Export graph data (JSON, GraphML)
- Search and highlight specific entities
"""

import json
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    nx = None

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    go = None

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QLabel, QLineEdit, QCheckBox, QGroupBox, QTextBrowser,
    QSplitter, QMessageBox, QFileDialog
)
from PySide6.QtCore import Signal, Qt

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False


class OntologyGraphWidget(QWidget):
    """
    Interactive ontology graph visualization widget.
    
    Displays entity relationships as an interactive network graph.
    
    Signals:
        node_selected(entity_id: str): Emitted when a node is clicked
        graph_updated(): Emitted when graph structure changes
    """
    
    node_selected = Signal(str)
    graph_updated = Signal()
    
    # Entity type colors
    ENTITY_COLORS = {
        "PERSON": "#FF6B6B",      # Red
        "ORG": "#4ECDC4",         # Teal
        "GPE": "#45B7D1",         # Blue
        "DATE": "#96CEB4",        # Green
        "MONEY": "#FFEAA7",       # Yellow
        "PRODUCT": "#DDA15E",     # Orange
        "EVENT": "#BC6C25",       # Brown
        "LAW": "#9B59B6",         # Purple
        "FAC": "#E74C3C",         # Dark Red
        "NORP": "#3498DB",        # Light Blue
        "CARDINAL": "#2ECC71",    # Light Green
        "ORDINAL": "#F39C12",     # Orange
        "QUANTITY": "#1ABC9C",    # Turquoise
        "TIME": "#E67E22",        # Deep Orange
        "PERCENT": "#95A5A6",     # Gray
        "DEFAULT": "#BDC3C7"      # Light Gray
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        if not NETWORKX_AVAILABLE:
            self._show_dependency_error("NetworkX")
            return
            
        if not PLOTLY_AVAILABLE:
            self._show_dependency_error("Plotly")
            return
        
        self.graph = nx.Graph()
        self.entities: Dict[str, Dict] = {}  # entity_id -> entity_data
        self.relationships: List[Dict] = []  # list of relationship dicts
        self.current_mode = "3D"  # "3D" or "2D"
        self.filtered_types: set = set()  # Types to show (empty = all)
        
        self._init_ui()
        
    def _show_dependency_error(self, lib_name: str):
        """Show error message for missing dependency."""
        layout = QVBoxLayout(self)
        label = QLabel(f"⚠️ {lib_name} not installed\n\n"
                      f"Install with: pip install {lib_name.lower()}")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 14px; color: #e74c3c;")
        layout.addWidget(label)
        
    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Top toolbar
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        # Main content area (graph + details)
        splitter = QSplitter(Qt.Horizontal)
        
        # Left: Graph visualization
        graph_container = QWidget()
        graph_layout = QVBoxLayout(graph_container)
        graph_layout.setContentsMargins(0, 0, 0, 0)
        
        if WEBENGINE_AVAILABLE:
            self.graph_view = QWebEngineView()
        else:
            self.graph_view = QTextBrowser()
            self.graph_view.setHtml("<h3>QWebEngineView not available</h3>"
                                   "<p>Install with: pip install PySide6-WebEngine</p>")
        
        graph_layout.addWidget(self.graph_view)
        splitter.addWidget(graph_container)
        
        # Right: Node details panel
        details_panel = self._create_details_panel()
        splitter.addWidget(details_panel)
        
        splitter.setStretchFactor(0, 3)  # Graph gets 75% width
        splitter.setStretchFactor(1, 1)  # Details gets 25% width
        
        layout.addWidget(splitter)
        
        # Bottom status bar
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("padding: 5px; background: #ecf0f1;")
        layout.addWidget(self.status_label)
        
    def _create_toolbar(self) -> QWidget:
        """Create the top toolbar with controls."""
        toolbar = QWidget()
        toolbar.setStyleSheet("background: #34495e; padding: 8px;")
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Visualization mode
        mode_label = QLabel("Mode:")
        mode_label.setStyleSheet("color: white; font-weight: bold;")
        layout.addWidget(mode_label)
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["3D Graph", "2D Graph"])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        layout.addWidget(self.mode_combo)
        
        layout.addWidget(self._create_separator())
        
        # Search
        search_label = QLabel("Search:")
        search_label.setStyleSheet("color: white; font-weight: bold;")
        layout.addWidget(search_label)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Entity name or ID...")
        self.search_input.setMaximumWidth(200)
        self.search_input.returnPressed.connect(self._on_search)
        layout.addWidget(self.search_input)
        
        search_btn = QPushButton("🔍 Find")
        search_btn.clicked.connect(self._on_search)
        layout.addWidget(search_btn)
        
        layout.addWidget(self._create_separator())
        
        # Filter by type
        filter_label = QLabel("Filter:")
        filter_label.setStyleSheet("color: white; font-weight: bold;")
        layout.addWidget(filter_label)
        
        self.type_filter = QComboBox()
        self.type_filter.addItem("All Types")
        self.type_filter.currentTextChanged.connect(self._on_filter_changed)
        layout.addWidget(self.type_filter)
        
        layout.addWidget(self._create_separator())
        
        # Actions
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_graph)
        layout.addWidget(refresh_btn)
        
        export_btn = QPushButton("💾 Export")
        export_btn.clicked.connect(self._on_export)
        layout.addWidget(export_btn)
        
        layout.addStretch()
        
        return toolbar
        
    def _create_separator(self) -> QLabel:
        """Create a vertical separator."""
        sep = QLabel("|")
        sep.setStyleSheet("color: #7f8c8d; font-size: 18px; padding: 0 5px;")
        return sep
        
    def _create_details_panel(self) -> QWidget:
        """Create the node details panel."""
        panel = QWidget()
        panel.setStyleSheet("background: #ecf0f1;")
        layout = QVBoxLayout(panel)
        
        # Title
        title = QLabel("📊 Node Details")
        title.setStyleSheet("font-size: 14px; font-weight: bold; padding: 10px; "
                           "background: #2c3e50; color: white;")
        layout.addWidget(title)
        
        # Details text
        self.details_text = QTextBrowser()
        self.details_text.setHtml("<p style='color: #7f8c8d; padding: 20px;'>"
                                 "Click a node to view details</p>")
        layout.addWidget(self.details_text)
        
        # Statistics
        stats_group = QGroupBox("Graph Statistics")
        stats_layout = QVBoxLayout(stats_group)
        
        self.stats_nodes = QLabel("Nodes: 0")
        self.stats_edges = QLabel("Edges: 0")
        self.stats_types = QLabel("Types: 0")
        self.stats_density = QLabel("Density: 0.0")
        
        for label in [self.stats_nodes, self.stats_edges, 
                     self.stats_types, self.stats_density]:
            label.setStyleSheet("padding: 3px;")
            stats_layout.addWidget(label)
        
        layout.addWidget(stats_group)
        
        return panel
        
    def set_data(self, entities: List[Dict], relationships: List[Dict]):
        """
        Set the graph data.
        
        Args:
            entities: List of entity dicts with keys:
                - id (str): Unique identifier
                - text (str): Entity text/name
                - type (str): Entity type (PERSON, ORG, etc.)
                - metadata (dict, optional): Additional data
                
            relationships: List of relationship dicts with keys:
                - source (str): Source entity ID
                - target (str): Target entity ID
                - type (str): Relationship type
                - confidence (float, optional): Confidence score
                - metadata (dict, optional): Additional data
        """
        self.entities = {e["id"]: e for e in entities}
        self.relationships = relationships
        
        # Clear and rebuild graph
        self.graph.clear()
        
        # Add nodes
        for entity_id, entity in self.entities.items():
            self.graph.add_node(
                entity_id,
                label=entity.get("text", entity_id),
                entity_type=entity.get("type", "UNKNOWN"),
                metadata=entity.get("metadata", {})
            )
        
        # Add edges
        for rel in relationships:
            if rel["source"] in self.entities and rel["target"] in self.entities:
                self.graph.add_edge(
                    rel["source"],
                    rel["target"],
                    rel_type=rel.get("type", "RELATED"),
                    confidence=rel.get("confidence", 1.0),
                    metadata=rel.get("metadata", {})
                )
        
        # Update type filter options
        entity_types = sorted(set(e.get("type", "UNKNOWN") for e in entities))
        current_filter = self.type_filter.currentText()
        self.type_filter.blockSignals(True)
        self.type_filter.clear()
        self.type_filter.addItem("All Types")
        self.type_filter.addItems(entity_types)
        self.type_filter.setCurrentText(current_filter)
        self.type_filter.blockSignals(False)
        
        # Update statistics
        self._update_statistics()
        
        # Emit signal
        self.graph_updated.emit()
        
    def refresh_graph(self):
        """Refresh the graph visualization."""
        if self.graph.number_of_nodes() == 0:
            self._set_status("No data to display", error=True)
            return
        
        self._set_status("Generating visualization...")
        
        try:
            if self.current_mode == "3D":
                html_content = self._generate_3d_graph()
            else:
                html_content = self._generate_2d_graph()
            
            if WEBENGINE_AVAILABLE:
                self.graph_view.setHtml(html_content)
            else:
                self.graph_view.setHtml(f"<pre>{html_content[:1000]}...</pre>")
            
            self._set_status(f"Displaying {self.graph.number_of_nodes()} nodes, "
                           f"{self.graph.number_of_edges()} edges")
            
        except Exception as e:
            self._set_status(f"Error: {str(e)}", error=True)
            
    def _generate_3d_graph(self) -> str:
        """Generate 3D graph visualization using Plotly."""
        # Apply filters
        filtered_graph = self._apply_filters()
        
        if filtered_graph.number_of_nodes() == 0:
            return "<h3>No nodes match the current filter</h3>"
        
        # Use spring layout for 3D positions
        pos = nx.spring_layout(filtered_graph, dim=3, seed=42)
        
        # Extract coordinates
        node_ids = list(filtered_graph.nodes())
        x_nodes = [pos[node][0] for node in node_ids]
        y_nodes = [pos[node][1] for node in node_ids]
        z_nodes = [pos[node][2] for node in node_ids]
        
        # Node colors based on type
        node_colors = []
        node_texts = []
        for node_id in node_ids:
            entity_type = filtered_graph.nodes[node_id].get("entity_type", "DEFAULT")
            node_colors.append(self.ENTITY_COLORS.get(entity_type, self.ENTITY_COLORS["DEFAULT"]))
            label = filtered_graph.nodes[node_id].get("label", node_id)
            node_texts.append(f"{label}<br>Type: {entity_type}")
        
        # Edge traces
        edge_traces = []
        for edge in filtered_graph.edges():
            x0, y0, z0 = pos[edge[0]]
            x1, y1, z1 = pos[edge[1]]
            
            edge_trace = go.Scatter3d(
                x=[x0, x1, None],
                y=[y0, y1, None],
                z=[z0, z1, None],
                mode='lines',
                line=dict(color='#95a5a6', width=2),
                hoverinfo='none',
                showlegend=False
            )
            edge_traces.append(edge_trace)
        
        # Node trace
        node_trace = go.Scatter3d(
            x=x_nodes,
            y=y_nodes,
            z=z_nodes,
            mode='markers+text',
            marker=dict(
                size=10,
                color=node_colors,
                line=dict(color='white', width=2)
            ),
            text=[filtered_graph.nodes[node].get("label", node) for node in node_ids],
            hovertext=node_texts,
            hoverinfo='text',
            textposition='top center',
            showlegend=False
        )
        
        # Create figure
        fig = go.Figure(data=edge_traces + [node_trace])
        
        fig.update_layout(
            title=dict(
                text=f"Entity Relationship Graph (3D) - {len(node_ids)} Nodes",
                x=0.5,
                xanchor='center'
            ),
            scene=dict(
                xaxis=dict(showbackground=False, showticklabels=False, title=''),
                yaxis=dict(showbackground=False, showticklabels=False, title=''),
                zaxis=dict(showbackground=False, showticklabels=False, title=''),
            ),
            showlegend=False,
            hovermode='closest',
            margin=dict(l=0, r=0, b=0, t=40),
            paper_bgcolor='white',
            plot_bgcolor='white'
        )
        
        return fig.to_html(include_plotlyjs='cdn', div_id="graph_3d")
        
    def _generate_2d_graph(self) -> str:
        """Generate 2D graph visualization using Plotly."""
        # Apply filters
        filtered_graph = self._apply_filters()
        
        if filtered_graph.number_of_nodes() == 0:
            return "<h3>No nodes match the current filter</h3>"
        
        # Use spring layout for 2D positions
        pos = nx.spring_layout(filtered_graph, seed=42)
        
        # Extract coordinates
        node_ids = list(filtered_graph.nodes())
        x_nodes = [pos[node][0] for node in node_ids]
        y_nodes = [pos[node][1] for node in node_ids]
        
        # Node colors based on type
        node_colors = []
        node_texts = []
        for node_id in node_ids:
            entity_type = filtered_graph.nodes[node_id].get("entity_type", "DEFAULT")
            node_colors.append(self.ENTITY_COLORS.get(entity_type, self.ENTITY_COLORS["DEFAULT"]))
            label = filtered_graph.nodes[node_id].get("label", node_id)
            node_texts.append(f"{label}<br>Type: {entity_type}")
        
        # Edge traces
        edge_x = []
        edge_y = []
        for edge in filtered_graph.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
        
        edge_trace = go.Scatter(
            x=edge_x,
            y=edge_y,
            mode='lines',
            line=dict(color='#95a5a6', width=1),
            hoverinfo='none',
            showlegend=False
        )
        
        # Node trace
        node_trace = go.Scatter(
            x=x_nodes,
            y=y_nodes,
            mode='markers+text',
            marker=dict(
                size=15,
                color=node_colors,
                line=dict(color='white', width=2)
            ),
            text=[filtered_graph.nodes[node].get("label", node)[:20] for node in node_ids],
            hovertext=node_texts,
            hoverinfo='text',
            textposition='top center',
            showlegend=False
        )
        
        # Create figure
        fig = go.Figure(data=[edge_trace, node_trace])
        
        fig.update_layout(
            title=dict(
                text=f"Entity Relationship Graph (2D) - {len(node_ids)} Nodes",
                x=0.5,
                xanchor='center'
            ),
            showlegend=False,
            hovermode='closest',
            margin=dict(l=20, r=20, b=20, t=60),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            paper_bgcolor='white',
            plot_bgcolor='white'
        )
        
        return fig.to_html(include_plotlyjs='cdn', div_id="graph_2d")
        
    def _apply_filters(self) -> nx.Graph:
        """Apply current filters and return filtered graph."""
        if not self.filtered_types:
            return self.graph.copy()
        
        # Filter nodes by type
        filtered_nodes = [
            node for node, data in self.graph.nodes(data=True)
            if data.get("entity_type") in self.filtered_types
        ]
        
        return self.graph.subgraph(filtered_nodes).copy()
        
    def _update_statistics(self):
        """Update graph statistics display."""
        num_nodes = self.graph.number_of_nodes()
        num_edges = self.graph.number_of_edges()
        
        # Count unique types
        types = set(data.get("entity_type", "UNKNOWN") 
                   for _, data in self.graph.nodes(data=True))
        num_types = len(types)
        
        # Calculate density
        density = nx.density(self.graph) if num_nodes > 1 else 0.0
        
        self.stats_nodes.setText(f"Nodes: {num_nodes}")
        self.stats_edges.setText(f"Edges: {num_edges}")
        self.stats_types.setText(f"Types: {num_types}")
        self.stats_density.setText(f"Density: {density:.3f}")
        
    def _on_mode_changed(self, mode_text: str):
        """Handle visualization mode change."""
        self.current_mode = "3D" if mode_text == "3D Graph" else "2D"
        self.refresh_graph()
        
    def _on_filter_changed(self, filter_text: str):
        """Handle entity type filter change."""
        if filter_text == "All Types":
            self.filtered_types.clear()
        else:
            self.filtered_types = {filter_text}
        
        self.refresh_graph()
        
    def _on_search(self):
        """Handle search for specific entity."""
        search_term = self.search_input.text().strip().lower()
        
        if not search_term:
            QMessageBox.information(self, "Search", "Please enter a search term")
            return
        
        # Search in entity IDs and labels
        matches = []
        for node_id, data in self.graph.nodes(data=True):
            label = data.get("label", "").lower()
            if search_term in node_id.lower() or search_term in label:
                matches.append((node_id, data))
        
        if not matches:
            QMessageBox.information(self, "Search", f"No entities found matching '{search_term}'")
            return
        
        # Show first match details
        node_id, data = matches[0]
        self._show_node_details(node_id, data)
        
        self._set_status(f"Found {len(matches)} match(es) for '{search_term}'")
        
    def _show_node_details(self, node_id: str, data: Dict):
        """Display detailed information about a node."""
        entity_type = data.get("entity_type", "UNKNOWN")
        label = data.get("label", node_id)
        metadata = data.get("metadata", {})
        
        # Get connected nodes
        neighbors = list(self.graph.neighbors(node_id))
        
        html = f"""
        <div style='padding: 15px;'>
            <h3 style='color: {self.ENTITY_COLORS.get(entity_type, "#333")};'>
                {label}
            </h3>
            <table style='width: 100%; border-collapse: collapse;'>
                <tr>
                    <td style='padding: 5px; font-weight: bold;'>ID:</td>
                    <td style='padding: 5px;'>{node_id}</td>
                </tr>
                <tr>
                    <td style='padding: 5px; font-weight: bold;'>Type:</td>
                    <td style='padding: 5px;'>{entity_type}</td>
                </tr>
                <tr>
                    <td style='padding: 5px; font-weight: bold;'>Connections:</td>
                    <td style='padding: 5px;'>{len(neighbors)}</td>
                </tr>
            </table>
            
            <h4>Metadata:</h4>
            <pre style='background: #ecf0f1; padding: 10px; border-radius: 3px;'>
{json.dumps(metadata, indent=2)}
            </pre>
            
            <h4>Connected Entities:</h4>
            <ul>
        """
        
        for neighbor_id in neighbors[:10]:  # Show max 10
            neighbor_data = self.graph.nodes[neighbor_id]
            neighbor_label = neighbor_data.get("label", neighbor_id)
            neighbor_type = neighbor_data.get("entity_type", "UNKNOWN")
            html += f"<li>{neighbor_label} ({neighbor_type})</li>"
        
        if len(neighbors) > 10:
            html += f"<li><i>... and {len(neighbors) - 10} more</i></li>"
        
        html += "</ul></div>"
        
        self.details_text.setHtml(html)
        self.node_selected.emit(node_id)
        
    def _on_export(self):
        """Export graph data to file."""
        if self.graph.number_of_nodes() == 0:
            QMessageBox.warning(self, "Export", "No graph data to export")
            return
        
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Graph",
            f"ontology_graph_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "GraphML (*.graphml);;JSON (*.json);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            if file_path.endswith('.json'):
                # Export as JSON
                data = {
                    "entities": [
                        {
                            "id": node_id,
                            **data
                        }
                        for node_id, data in self.graph.nodes(data=True)
                    ],
                    "relationships": [
                        {
                            "source": edge[0],
                            "target": edge[1],
                            **data
                        }
                        for edge in self.graph.edges(data=True)
                        for data in [edge[2]]
                    ]
                }
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
            else:
                # Export as GraphML
                nx.write_graphml(self.graph, file_path)
            
            QMessageBox.information(self, "Export", f"Graph exported to:\n{file_path}")
            self._set_status(f"Exported to {file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export:\n{str(e)}")
            self._set_status(f"Export failed: {str(e)}", error=True)
            
    def _set_status(self, message: str, error: bool = False):
        """Update status bar message."""
        color = "#e74c3c" if error else "#27ae60"
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"padding: 5px; background: #ecf0f1; color: {color};")


# Example usage and testing
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    
    # Sample data
    entities = [
        {"id": "e1", "text": "John Doe", "type": "PERSON"},
        {"id": "e2", "text": "Acme Corp", "type": "ORG"},
        {"id": "e3", "text": "New York", "type": "GPE"},
        {"id": "e4", "text": "2024-01-15", "type": "DATE"},
        {"id": "e5", "text": "$1,000,000", "type": "MONEY"},
        {"id": "e6", "text": "Jane Smith", "type": "PERSON"},
        {"id": "e7", "text": "TechCo", "type": "ORG"},
        {"id": "e8", "text": "California", "type": "GPE"},
    ]
    
    relationships = [
        {"source": "e1", "target": "e2", "type": "WORKS_FOR", "confidence": 0.95},
        {"source": "e1", "target": "e3", "type": "LOCATED_IN", "confidence": 0.85},
        {"source": "e2", "target": "e5", "type": "RECEIVED", "confidence": 0.90},
        {"source": "e2", "target": "e4", "type": "DATED", "confidence": 0.80},
        {"source": "e6", "target": "e7", "type": "WORKS_FOR", "confidence": 0.92},
        {"source": "e7", "target": "e8", "type": "LOCATED_IN", "confidence": 0.88},
        {"source": "e1", "target": "e6", "type": "KNOWS", "confidence": 0.75},
        {"source": "e2", "target": "e7", "type": "PARTNER_WITH", "confidence": 0.70},
    ]
    
    widget = OntologyGraphWidget()
    widget.setWindowTitle("Ontology Graph Visualization")
    widget.resize(1200, 800)
    widget.set_data(entities, relationships)
    widget.refresh_graph()
    widget.show()
    
    sys.exit(app.exec())
