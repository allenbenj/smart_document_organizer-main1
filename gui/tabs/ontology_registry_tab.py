from __future__ import annotations

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

from ..services import api_client


class OntologyRegistryTab(QWidget):
    """GUI connector for ontology registry lifecycle operations."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()
        self.refresh_registry()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Ontology Registry")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)

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

        layout.addWidget(control_group)

        self.output = QTextBrowser()
        layout.addWidget(self.output)

    def _connect_signals(self) -> None:
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
        except Exception as e:
            QMessageBox.critical(self, "Registry Error", str(e))

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
        except Exception as e:
            QMessageBox.critical(self, "Create Version Error", str(e))

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
            QMessageBox.warning(self, "Validation", "Version must be an integer.")
        except Exception as e:
            QMessageBox.critical(self, "Activate Error", str(e))

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
            QMessageBox.warning(self, "Validation", "Version must be an integer.")
        except Exception as e:
            QMessageBox.critical(self, "Deprecate Error", str(e))
