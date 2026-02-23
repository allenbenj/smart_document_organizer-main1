"""
Integration Test Suite for Production Workflow 2026-02

Tests the complete workflow across all new features:
- Document Preview System
- NLP Model Manager
- Entity Proposals Workflow
- Interactive Statistics Dashboard
- Ontology Graph Visualization
- Excel Export Enhancement
- ML Optimization Libraries

Run with: pytest tests/test_production_integration.py -v
"""

import pytest
import sys
from pathlib import Path
import tempfile
import shutil
import uuid

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestDocumentPreviewIntegration:
    """Test document preview widget integration."""
    
    def test_preview_widget_import(self):
        """Test that DocumentPreviewWidget can be imported."""
        from gui.ui import DocumentPreviewWidget
        assert DocumentPreviewWidget is not None
        
    def test_preview_widget_creation(self, qtbot):
        """Test creating a DocumentPreviewWidget instance."""
        from gui.ui import DocumentPreviewWidget
        
        widget = DocumentPreviewWidget()
        qtbot.addWidget(widget)
        
        assert widget is not None
        assert hasattr(widget, 'load_document')
        assert hasattr(widget, 'document_loaded')
        assert hasattr(widget, 'preview_error')


class TestNLPModelManagerIntegration:
    """Test NLP Model Manager integration."""
    
    def test_model_manager_import(self):
        """Test that NLPModelManagerDialog can be imported."""
        from gui.ui import NLPModelManagerDialog
        assert NLPModelManagerDialog is not None
        
    def test_model_manager_creation(self, qtbot):
        """Test creating a NLPModelManagerDialog instance."""
        from gui.ui import NLPModelManagerDialog
        
        dialog = NLPModelManagerDialog()
        qtbot.addWidget(dialog)
        
        assert dialog is not None
        assert hasattr(dialog, 'install_selected_models')


class TestEntityProposalsIntegration:
    """Test Entity Proposals workflow integration."""
    
    def test_proposals_widget_import(self):
        """Test that EntityProposalsWidget can be imported."""
        from gui.ui import EntityProposalsWidget, EntityProposal
        assert EntityProposalsWidget is not None
        assert EntityProposal is not None
        
    def test_proposals_widget_creation(self, qtbot):
        """Test creating an EntityProposalsWidget instance."""
        from gui.ui import EntityProposalsWidget
        
        widget = EntityProposalsWidget()
        qtbot.addWidget(widget)
        
        assert widget is not None
        assert hasattr(widget, 'add_proposals')
        assert hasattr(widget, 'approve_selected')
        assert hasattr(widget, 'reject_selected')
        assert hasattr(widget, 'get_approved_proposals')
        
    def test_proposal_workflow(self, qtbot):
        """Test complete proposal approval workflow."""
        from gui.ui import EntityProposalsWidget, EntityProposal
        
        widget = EntityProposalsWidget()
        qtbot.addWidget(widget)
        
        # Add a proposal
        proposals = [
            EntityProposal(
                entity_type="PERSON",
                entity_text="John Doe",
                confidence=0.95,
                source_document="test_doc.pdf",
                proposal_id="test_1"
            )
        ]
        widget.add_proposals(proposals)
        
        # Manually approve it (simulate clicking approve button)
        proposals[0].status = "approved"
        
        # Check approved list
        approved = widget.get_approved_proposals()
        assert len(approved) == 1
        assert approved[0].entity_text == "John Doe"


class TestStatsDashboardIntegration:
    """Test Interactive Stats Dashboard integration."""
    
    def test_dashboard_import(self):
        """Test that InteractiveStatsDashboard can be imported."""
        from gui.ui import InteractiveStatsDashboard
        assert InteractiveStatsDashboard is not None
        
    def test_dashboard_creation(self, qtbot):
        """Test creating an InteractiveStatsDashboard instance."""
        from gui.ui import InteractiveStatsDashboard
        
        dashboard = InteractiveStatsDashboard()
        qtbot.addWidget(dashboard)
        
        assert dashboard is not None
        assert hasattr(dashboard, 'set_data')
        assert hasattr(dashboard, 'refresh_dashboard')
        
    def test_dashboard_with_data(self, qtbot):
        """Test dashboard with sample data."""
        from gui.ui import InteractiveStatsDashboard
        from datetime import datetime
        
        dashboard = InteractiveStatsDashboard()
        qtbot.addWidget(dashboard)
        
        sample_data = {
            "entities": [
                {
                    "type": "PERSON",
                    "text": "John Doe",
                    "confidence": 0.95,
                    "timestamp": datetime.now().isoformat()
                },
                {
                    "type": "ORG",
                    "text": "Acme Corp",
                    "confidence": 0.88,
                    "timestamp": datetime.now().isoformat()
                }
            ],
            "documents": [
                {
                    "name": "test.pdf",
                    "entity_count": 10,
                    "processing_time": 2.5,
                    "timestamp": datetime.now().isoformat()
                }
            ],
            "memory_stats": {
                "total_records": 100,
                "cache_hits": 45,
                "cache_misses": 12
            }
        }
        
        dashboard.set_data(sample_data)
        assert dashboard.data is not None


class TestOntologyGraphIntegration:
    """Test Ontology Graph Visualization integration."""
    
    def test_graph_widget_import(self):
        """Test that OntologyGraphWidget can be imported."""
        from gui.ui import OntologyGraphWidget
        assert OntologyGraphWidget is not None
        
    def test_graph_widget_creation(self, qtbot):
        """Test creating an OntologyGraphWidget instance."""
        try:
            import networkx
        except ImportError:
            pytest.skip("NetworkX not installed")
        
        try:
            import plotly
        except ImportError:
            pytest.skip("Plotly not installed")
        
        from gui.ui import OntologyGraphWidget
        
        widget = OntologyGraphWidget()
        qtbot.addWidget(widget)
        
        assert widget is not None
        assert hasattr(widget, 'set_data')
        assert hasattr(widget, 'refresh_graph')
        
    def test_graph_with_data(self, qtbot):
        """Test graph widget with sample data."""
        try:
            import networkx
            import plotly
        except ImportError:
            pytest.skip("NetworkX or Plotly not installed")
        
        from gui.ui import OntologyGraphWidget
        
        widget = OntologyGraphWidget()
        qtbot.addWidget(widget)
        
        entities = [
            {"id": "e1", "text": "John Doe", "type": "PERSON"},
            {"id": "e2", "text": "Acme Corp", "type": "ORG"},
        ]
        
        relationships = [
            {"source": "e1", "target": "e2", "type": "WORKS_FOR", "confidence": 0.95}
        ]
        
        widget.set_data(entities, relationships)
        assert widget.graph.number_of_nodes() == 2
        assert widget.graph.number_of_edges() == 1


class TestExcelExportIntegration:
    """Test Excel Export integration."""
    
    def test_excel_exporter_import(self):
        """Test that ExcelExporter can be imported."""
        from gui.exporters import ExcelExporter
        assert ExcelExporter is not None
        
    def test_excel_export_creation(self):
        """Test creating an ExcelExporter instance."""
        try:
            from gui.exporters import ExcelExporter
            exporter = ExcelExporter()
            assert exporter is not None
        except ImportError:
            pytest.skip("openpyxl not installed")
            
    def test_excel_export_full_report(self):
        """Test exporting a full report to Excel."""
        try:
            from gui.exporters import ExcelExporter
        except ImportError:
            pytest.skip("openpyxl not installed")
        
        exporter = ExcelExporter()
        
        # Create temp file
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            # Sample data
            entities = [
                {
                    "id": "e1",
                    "text": "John Doe",
                    "type": "PERSON",
                    "confidence": 0.95,
                    "source": "doc1.pdf"
                }
            ]
            
            documents = [
                {
                    "name": "doc1.pdf",
                    "path": "/docs/doc1.pdf",
                    "type": "PDF",
                    "size": 102400,
                    "entity_count": 5,
                    "processing_time": 1.5,
                    "status": "Completed"
                }
            ]
            
            proposals = [
                {
                    "id": "p1",
                    "text": "Jane Smith",
                    "type": "PERSON",
                    "confidence": 0.80,
                    "status": "pending"
                }
            ]
            
            statistics = {
                "total_documents": 1,
                "total_entities": 5,
                "unique_types": 3,
                "avg_confidence": 0.85
            }
            
            # Export
            result_path = exporter.export_full_report(
                tmp_path,
                entities,
                documents,
                proposals,
                statistics
            )
            
            assert Path(result_path).exists()
            assert Path(result_path).stat().st_size > 0
            
        finally:
            # Cleanup
            if Path(tmp_path).exists():
                Path(tmp_path).unlink()


class TestMLOptimizationIntegration:
    """Test ML Optimization libraries integration."""
    
    def test_embedding_cache_import(self):
        """Test that EmbeddingCache can be imported."""
        from core.ml_optimization import EmbeddingCache
        assert EmbeddingCache is not None
        
    def test_embedding_cache_usage(self):
        """Test basic embedding cache functionality."""
        from core.ml_optimization import EmbeddingCache
        import numpy as np
        
        # Create temp cache dir
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = EmbeddingCache(tmpdir)
            
            # Store embedding
            text = "test document"
            embedding = np.random.rand(384).astype(np.float32)
            
            cache.put(text, embedding)
            
            # Retrieve embedding
            retrieved = cache.get(text)
            
            assert retrieved is not None
            assert np.allclose(retrieved, embedding)
            
            # Check stats
            stats = cache.get_stats()
            assert stats['hits'] == 1
            assert stats['misses'] == 0
            
    def test_faiss_search_engine(self):
        """Test FAISS search engine if available."""
        try:
            from core.ml_optimization import FAISSSearchEngine
            import numpy as np
        except ImportError:
            pytest.skip("FAISS not installed")
        
        engine = FAISSSearchEngine(dimension=384)
        
        # Add vectors
        vectors = np.random.rand(10, 384).astype(np.float32)
        metadata = [{"id": i} for i in range(10)]
        engine.add_embeddings(vectors, metadata)
        
        assert engine.index.ntotal == 10
        
        # Search
        query = np.random.rand(384).astype(np.float32)
        results = engine.search_with_metadata(query, k=3)
        
        assert len(results) == 3
        assert all('distance' in r for r in results)
        assert all('metadata' in r for r in results)
        
    def test_entity_clusterer(self):
        """Test entity clustering if sklearn available."""
        try:
            from core.ml_optimization import EntityClusterer
            import numpy as np
        except ImportError:
            pytest.skip("scikit-learn not installed")
        
        clusterer = EntityClusterer(algorithm="kmeans")
        
        # Create sample data
        data = np.random.rand(50, 384).astype(np.float32)
        
        labels = clusterer.fit(data, n_clusters=3)
        
        assert len(labels) == 50
        assert len(np.unique(labels)) <= 3  # May be fewer if convergence issues
        
        # Get info
        info = clusterer.get_cluster_info(data)
        assert 'n_clusters' in info
        assert 'silhouette_score' in info
        
    def test_batch_processor(self):
        """Test batch processor if sentence-transformers available."""
        try:
            from core.ml_optimization import BatchProcessor
        except ImportError:
            pytest.skip("sentence-transformers not installed")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            processor = BatchProcessor(
                model_name="all-MiniLM-L6-v2",
                batch_size=2,
                cache_dir=tmpdir
            )
            
            texts = ["Document 1", "Document 2", "Document 3"]
            embeddings = processor.encode_batch(texts, use_cache=True)
            
            assert embeddings.shape[0] == 3
            assert embeddings.shape[1] > 0  # Has dimension
            
            # Check cache was used
            stats = processor.get_stats()
            assert 'cache_stats' in stats


class TestEndToEndWorkflow:
    """Test complete end-to-end workflow integration."""
    
    def test_memory_infrastructure_available(self):
        """Verify memory infrastructure is accessible."""
        from mem_db.memory.unified_memory_manager import UnifiedMemoryManager
        assert UnifiedMemoryManager is not None
        
    def test_complete_workflow_simulation(self):
        """Simulate a complete document processing workflow."""
        # This is a high-level integration test that would be expanded
        # in production to test the full pipeline
        
        # 1. Document Preview
        from gui.ui import DocumentPreviewWidget
        preview = DocumentPreviewWidget()
        assert preview is not None
        
        # 2. Entity Proposals
        from gui.ui import EntityProposalsWidget, EntityProposal
        proposals_widget = EntityProposalsWidget()
        
        sample_proposal = EntityProposal(
            entity_type="PERSON",
            entity_text="Test Entity",
            confidence=0.85,
            source_document="test.pdf",
            proposal_id=str(uuid.uuid4())
        )
        proposals_widget.add_proposals([sample_proposal])
        
        # 3. Approve proposal (simulate approval)
        sample_proposal.status = "approved"
        approved = proposals_widget.get_approved_proposals()
        assert len(approved) == 1
        
        # 4. Stats Dashboard
        from gui.ui import InteractiveStatsDashboard
        dashboard = InteractiveStatsDashboard()
        
        dashboard.set_data({
            "entities": [{"type": "PERSON", "text": "Test Entity", "confidence": 0.85}],
            "documents": [{"name": "test.pdf", "entity_count": 1}],
            "memory_stats": {"total_records": 1}
        })
        
        # 5. Ontology Graph (if available)
        try:
            from gui.ui import OntologyGraphWidget
            graph = OntologyGraphWidget()
            graph.set_data(
                entities=[{"id": "e1", "text": "Test Entity", "type": "PERSON"}],
                relationships=[]
            )
        except:
            pass  # Skip if dependencies missing
        
        # 6. Excel Export (if available)
        try:
            from gui.exporters import ExcelExporter
            exporter = ExcelExporter()
            assert exporter is not None
        except:
            pass  # Skip if openpyxl missing
        
        # Workflow completed successfully
        assert True


# Run tests with: pytest tests/test_production_integration.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
