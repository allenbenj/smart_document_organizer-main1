from __future__ import annotations

import json
import logging # Added logging
from typing import Any, Optional

try:
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import (
        QComboBox,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QTextBrowser,
        QVBoxLayout,
        QWidget,
    )
    from PySide6.QtCore import Qt, Signal
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False
    QWidget = object  # type: ignore

try:
    import requests # Added requests
    import requests.exceptions # Added requests.exceptions
except ImportError:
    requests = None  # type: ignore


from ..services import api_client
from gui.core.base_tab import BaseTab

logger = logging.getLogger(__name__) # Initialized logger


class OntologyRegistryTab(BaseTab):
    """GUI connector for ontology registry lifecycle operations."""

    def __init__(self, asyncio_thread: Optional[Any] = None, parent=None):
        super().__init__("Ontology Registry", asyncio_thread, parent)
        self._setup_ui()
        self._connect_signals()
        self.refresh_registry()

    def setup_ui(self) -> None:
        title = QLabel("Ontology Registry")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.main_layout.addWidget(title)

        control_group = QGroupBox("Version Lifecycle")
        control_layout = QVBoxLayout(control_group)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Ontology Type:"))
        self.ontology_type_combo = QComboBox()
        self.ontology_type_combo.addItems(
            ["objective", "heuristic", "domain", "constraint", "schema", "taxonomy"]
        )
        type_row.addWidget(self.ontology_type_combo)
        control_layout.addLayout(type_row)

        version_row = QHBoxLayout()
        version_row.addWidget(QLabel("Version:"))
        self.version_input = QLineEdit()
        self.version_input.setPlaceholderText("1")
        version_row.addWidget(self.version_input)
        control_layout.addLayout(version_row)

        desc_row = QHBoxLayout()
        desc_row.addWidget(QLabel("Description:"))
        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("Registry change note")
        desc_row.addWidget(self.description_input)
        control_layout.addLayout(desc_row)

        button_row = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        self.create_button = QPushButton("Create Version")
        self.activate_button = QPushButton("Activate")
        self.deprecate_button = QPushButton("Deprecate")
        button_row.addWidget(self.refresh_button)
        button_row.addWidget(self.create_button)
        button_row.addWidget(self.activate_button)
        button_row.addWidget(self.deprecate_button)
        control_layout.addLayout(button_row)

        self.main_layout.addWidget(control_group)

        self.output = QTextBrowser()
        self.main_layout.addWidget(self.output)

    def connect_signals(self) -> None:
        self.refresh_button.clicked.connect(self.refresh_registry)
        self.create_button.clicked.connect(self.create_version)
        self.activate_button.clicked.connect(self.activate_version)
        self.deprecate_button.clicked.connect(self.deprecate_version)

    def _selected_type(self) -> str:
        return self.ontology_type_combo.currentText().strip()

    def _selected_version(self) -> int:
        return int(self.version_input.text().strip())

    def refresh_registry(self) -> None:
        try:
            result = api_client.list_ontology_registry()
            items = result.get("items", [])
            self.output.clear()
            self.output.append(f"Registry entries: {len(items)}")
            for item in items:
                self.output.append(
                    f"- {item.get('ontology_type')}: "
                    f"v{item.get('version')} ({item.get('status')})"
                )
        except requests.exceptions.RequestException as e:
            logger.error(f"API connection error refreshing ontology registry: {e}")
            QMessageBox.critical(self, "Registry Error", f"API connection error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid API response refreshing ontology registry: {e}")
            QMessageBox.critical(self, "Registry Error", f"Invalid API response: {e}")
        except RuntimeError as e:
            logger.error(f"Runtime error refreshing ontology registry: {e}")
            QMessageBox.critical(self, "Registry Error", f"Runtime error: {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred refreshing ontology registry: {e}")
            QMessageBox.critical(self, "Registry Error", f"An unexpected error occurred: {e}")

    def create_version(self) -> None:
        try:
            result = api_client.create_ontology_registry_version(
                ontology_type=self._selected_type(),
                description=self.description_input.text().strip() or None,
            )
            item = result.get("item", {})
            self.output.append(
                f"Created {item.get('ontology_type')} v{item.get('version')} "
                f"({item.get('status')})."
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"API connection error creating ontology version: {e}")
            QMessageBox.critical(self, "Create Version Error", f"API connection error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid API response creating ontology version: {e}")
            QMessageBox.critical(self, "Create Version Error", f"Invalid API response: {e}")
        except RuntimeError as e:
            logger.error(f"Runtime error creating ontology version: {e}")
            QMessageBox.critical(self, "Create Version Error", f"Runtime error: {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred creating ontology version: {e}")
            QMessageBox.critical(self, "Create Version Error", f"An unexpected error occurred: {e}")

    def activate_version(self) -> None:
        try:
            result = api_client.activate_ontology_registry_version(
                ontology_type=self._selected_type(),
                version=self._selected_version(),
            )
            item = result.get("item", {})
            self.output.append(
                f"Activated {item.get('ontology_type')} v{item.get('version')}."
            )
        except ValueError:
            logger.warning("Validation error: Version must be an integer during activation.")
            QMessageBox.warning(self, "Validation", "Version must be an integer.")
        except requests.exceptions.RequestException as e:
            logger.error(f"API connection error activating ontology version: {e}")
            QMessageBox.critical(self, "Activate Error", f"API connection error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid API response activating ontology version: {e}")
            QMessageBox.critical(self, "Activate Error", f"Invalid API response: {e}")
        except RuntimeError as e:
            logger.error(f"Runtime error activating ontology version: {e}")
            QMessageBox.critical(self, "Activate Error", f"Runtime error: {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred activating ontology version: {e}")
            QMessageBox.critical(self, "Activate Error", f"An unexpected error occurred: {e}")

    def deprecate_version(self) -> None:
        try:
            result = api_client.deprecate_ontology_registry_version(
                ontology_type=self._selected_type(),
                version=self._selected_version(),
            )
            item = result.get("item", {})
            self.output.append(
                f"Deprecated {item.get('ontology_type')} v{item.get('version')}."
            )
        except ValueError:
            logger.warning("Validation error: Version must be an integer during deprecation.")
            QMessageBox.warning(self, "Validation", "Version must be an integer.")
        except requests.exceptions.RequestException as e:
            logger.error(f"API connection error deprecating ontology version: {e}")
            QMessageBox.critical(self, "Deprecate Error", f"API connection error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid API response deprecating ontology version: {e}")
            QMessageBox.critical(self, "Deprecate Error", f"Invalid API response: {e}")
        except RuntimeError as e:
            logger.error(f"Runtime error deprecating ontology version: {e}")
            QMessageBox.critical(self, "Deprecate Error", f"Runtime error: {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred deprecating ontology version: {e}")
            QMessageBox.critical(self, "Deprecate Error", f"An unexpected error occurred: {e}")
