"""
GUI Action Path Smoke Tests - Verify high-level GUI workflows.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

class TestGuiActionPaths(unittest.TestCase):
    """
    Smoke tests for the full GUI action paths.
    Mocks the API and UI components to verify the orchestration logic.
    """

    @patch('gui.services.ApiClient._make_request')
    def test_process_documents_path(self, mock_request):
        """Test the 'Process Documents' action path."""
        from gui.tabs.document_processing_tab import DocumentProcessingTab
        from PySide6.QtWidgets import QApplication
        
        # Need a QApplication instance for QWidget creation
        app = QApplication.instance() or QApplication(sys.argv)
        
        # Mock API response for batch processing
        mock_request.return_value = {
            "success": True,
            "processed": 1,
            "failed": 0,
            "files": [
                {
                    "filename": "test.pdf",
                    "success": True,
                    "processed_document": {
                        "content": "Sample content",
                        "metadata": {"author": "Test"}
                    }
                }
            ]
        }
        
        tab = DocumentProcessingTab()
        tab.selected_files = ["test.pdf"]
        
        # Mock the worker
        with patch('gui.tabs.document_processing_tab.UploadManyFilesWorker') as MockWorker:
            instance = MockWorker.return_value
            # Ensure mock signals have 'connect' method
            instance.finished_ok = MagicMock()
            instance.finished_err = MagicMock()
            instance.finished = MagicMock()
            
            # Execute the action
            tab.start_processing()
            
            # Verify worker was started with correct args
            MockWorker.assert_called_once()
            instance.start.assert_called_once()
            
            # Simulate worker completion by calling the handler directly
            normalized_result = {
                "success": True,
                "processed_count": 1,
                "failed_count": 0,
                "items": [{
                    "filename": "test.pdf",
                    "success": True,
                    "content": "Sample content",
                    "metadata": {"author": "Test"}
                }]
            }
            tab.on_processing_finished(normalized_result)
            
            # Verify results were stored and displayed
            self.assertIsNotNone(tab.current_results)
            self.assertEqual(tab.current_results["processed_count"], 1)
            self.assertIn("test.pdf", tab.results_browser.toHtml())

    @patch('gui.services.ApiClient.get')
    def test_review_proposals_path(self, mock_get):
        """Test the 'Review Proposals' action path in Organization Tab."""
        from gui.tabs.organization_tab import OrganizationTab
        from PySide6.QtWidgets import QApplication
        import time
        
        app = QApplication.instance() or QApplication(sys.argv)
        
        # Mock API response for proposals
        mock_get.return_value = {
            "items": [
                {
                    "id": 1,
                    "current_path": "inbox/doc1.pdf",
                    "proposed_folder": "legal",
                    "proposed_filename": "doc1_legal.pdf",
                    "confidence": 0.95
                }
            ]
        }
        
        tab = OrganizationTab()
        
        # Use a simpler way to test the result of the non-blocking call
        # Mock the worker finished signal
        with patch('gui.tabs.organization_tab.LoadProposalsWorker') as MockWorker:
            instance = MockWorker.return_value
            instance.finished_ok = MagicMock()
            instance.finished_err = MagicMock()
            instance.finished = MagicMock()
            
            tab.org_load_proposals()
            
            # Simulate worker completion
            tab.all_proposals_cache = mock_get.return_value["items"]
            tab.apply_search_filter(silent=True)
            
            # Verify table was populated
            self.assertEqual(tab.org_table.rowCount(), 1)
            self.assertEqual(tab.org_table.item(0, 1).text(), "1")
            self.assertEqual(len(tab.proposals_cache), 1)

if __name__ == "__main__":
    unittest.main()
