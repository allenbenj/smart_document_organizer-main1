"""
GUI Smoke Tests - Basic import and instantiation checks for GUI components.
"""

import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_gui_dashboard_import():
    """Test that gui_dashboard can be imported without errors."""
    try:
        import gui.gui_dashboard
        assert hasattr(gui.gui_dashboard, 'LegalAIDashboard')
        assert hasattr(gui.gui_dashboard, 'AsyncioThread')
        print("✓ gui_dashboard import OK")
    except ImportError as e:
        print(f"✗ gui_dashboard import failed: {e}")
        return False
    return True


def test_gui_tabs_import():
    """Test that all GUI tabs can be imported without errors."""
    try:
        from gui.tabs import (
            classification_tab,
            document_processing_tab,
            embedding_operations_tab,
            entity_extraction_tab,
            expert_prompts_tab,
            knowledge_graph_tab,
            legal_reasoning_tab,
            pipelines_tab,
            semantic_analysis_tab,
            vector_search_tab,
        )
        # Check that each has a main class
        assert hasattr(classification_tab, 'ClassificationTab')
        assert hasattr(document_processing_tab, 'DocumentOrganizationTab')
        assert hasattr(embedding_operations_tab, 'EmbeddingOperationsTab')
        assert hasattr(entity_extraction_tab, 'EntityExtractionTab')
        assert hasattr(expert_prompts_tab, 'ExpertPromptsTab')
        assert hasattr(knowledge_graph_tab, 'KnowledgeGraphTab')
        assert hasattr(legal_reasoning_tab, 'LegalReasoningTab')
        assert hasattr(pipelines_tab, 'PipelinesTab')
        assert hasattr(semantic_analysis_tab, 'SemanticAnalysisTab')
        assert hasattr(vector_search_tab, 'VectorSearchTab')
        print("✓ gui_tabs import OK")
    except ImportError as e:
        print(f"✗ gui_tabs import failed: {e}")
        return False
    return True


def test_workers_import():
    """Test that workers can be imported."""
    try:
        from gui.tabs.workers import (
            UploadFileWorker,
            UploadFolderWorker,
            UploadManyFilesWorker,
            KGImportFromTextWorker,
            SemanticAnalysisWorker,
            EntityExtractionWorker,
            LegalReasoningWorker,
            EmbeddingWorker,
            DocumentOrganizationWorker,
            VectorIndexWorker,
            KGFromFilesWorker,
            PipelineRunnerWorker,
        )
        # Check they are QThread subclasses
        import PySide6.QtCore as QtCore
        assert issubclass(UploadFileWorker, QtCore.QThread)
        assert issubclass(SemanticAnalysisWorker, QtCore.QThread)
        print("✓ workers import OK")
    except ImportError as e:
        print(f"✗ workers import failed: {e}")
        return False
    return True


def test_ui_components_import():
    """Test that UI components can be imported."""
    try:
        from gui.ui import RunConsolePanel, SystemHealthStrip
        # Just check they exist
        assert RunConsolePanel is not None
        assert SystemHealthStrip is not None
        print("✓ ui_components import OK")
    except ImportError as e:
        print(f"✗ ui_components import failed: {e}")
        return False
    return True


if __name__ == "__main__":
    print("Running GUI smoke tests...")
    results = []
    results.append(test_gui_dashboard_import())
    results.append(test_gui_tabs_import())
    results.append(test_workers_import())
    results.append(test_ui_components_import())

    passed = sum(results)
    total = len(results)
    print(f"\nResults: {passed}/{total} tests passed")
    if passed == total:
        print("✓ All GUI smoke tests passed")
        sys.exit(0)
    else:
        print("✗ Some GUI smoke tests failed")
        sys.exit(1)