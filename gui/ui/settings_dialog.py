"""
Settings Dialog
===============
Provides a GUI for viewing and editing application configuration.
"""

import logging
from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QWidget,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QComboBox,
    QLabel,
    QPushButton,
    QMessageBox,
    QGroupBox,
)
from PySide6.QtCore import Qt

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Application settings dialog backed by ConfigurationManager."""

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.setWindowTitle("Settings")
        self.setMinimumSize(520, 440)
        self._build_ui()
        self._load_values()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_general_tab(), "General")
        self.tabs.addTab(self._build_agents_tab(), "Agents")
        self.tabs.addTab(self._build_vector_tab(), "Vector / Embedding")
        self.tabs.addTab(self._build_memory_tab(), "Memory")
        layout.addWidget(self.tabs)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self._save)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_cancel)
        layout.addLayout(btn_row)

    # -- General tab --
    def _build_general_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self.env_combo = QComboBox()
        self.env_combo.addItems(["development", "production", "testing"])
        form.addRow("Environment:", self.env_combo)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        form.addRow("API Key:", self.api_key_edit)

        return w

    # -- Agents tab --
    def _build_agents_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self.cache_ttl_spin = QSpinBox()
        self.cache_ttl_spin.setRange(0, 86400)
        self.cache_ttl_spin.setSuffix(" s")
        form.addRow("Cache TTL:", self.cache_ttl_spin)

        self.cb_legal_reasoning = QCheckBox("Legal Reasoning")
        self.cb_entity_extractor = QCheckBox("Entity Extractor")
        self.cb_irac = QCheckBox("IRAC Analysis")
        self.cb_toulmin = QCheckBox("Toulmin Analysis")
        self.cb_registry = QCheckBox("Agent Registry")

        group = QGroupBox("Enabled Agents")
        gl = QVBoxLayout(group)
        for cb in (
            self.cb_legal_reasoning,
            self.cb_entity_extractor,
            self.cb_irac,
            self.cb_toulmin,
            self.cb_registry,
        ):
            gl.addWidget(cb)
        form.addRow(group)

        return w

    # -- Vector tab --
    def _build_vector_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self.vec_dim_spin = QSpinBox()
        self.vec_dim_spin.setRange(1, 4096)
        form.addRow("Dimension:", self.vec_dim_spin)

        self.vec_model_edit = QLineEdit()
        form.addRow("Embedding Model:", self.vec_model_edit)

        self.cb_use_st = QCheckBox("Use sentence-transformers")
        form.addRow(self.cb_use_st)

        return w

    # -- Memory tab --
    def _build_memory_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self.approval_spin = QDoubleSpinBox()
        self.approval_spin.setRange(0.0, 1.0)
        self.approval_spin.setSingleStep(0.05)
        self.approval_spin.setDecimals(2)
        form.addRow("Approval Threshold:", self.approval_spin)

        return w

    # ------------------------------------------------------------ Load/Save
    def _load_values(self):
        env = self.config.get_str("env", "development")
        idx = self.env_combo.findText(env)
        if idx >= 0:
            self.env_combo.setCurrentIndex(idx)

        self.api_key_edit.setText(self.config.get_str("security.api_key", ""))

        self.cache_ttl_spin.setValue(
            self.config.get_int("agents.cache_ttl_seconds", 300)
        )

        self.cb_legal_reasoning.setChecked(
            self.config.get_bool("agents.enable_legal_reasoning")
        )
        self.cb_entity_extractor.setChecked(
            self.config.get_bool("agents.enable_entity_extractor")
        )
        self.cb_irac.setChecked(self.config.get_bool("agents.enable_irac"))
        self.cb_toulmin.setChecked(self.config.get_bool("agents.enable_toulmin"))
        self.cb_registry.setChecked(self.config.get_bool("agents.enable_registry"))

        self.vec_dim_spin.setValue(self.config.get_int("vector.dimension", 384))
        self.vec_model_edit.setText(
            self.config.get_str("vector.embedding_model", "all-MiniLM-L6-v2")
        )
        self.cb_use_st.setChecked(
            self.config.get_bool("vector.use_sentence_transformers", True)
        )

        self.approval_spin.setValue(
            self.config.get_float("memory.approval_threshold", 0.7)
        )

    def _save(self):
        self.config.set("env", self.env_combo.currentText())
        api_key = self.api_key_edit.text().strip()
        if api_key:
            self.config.set("security.api_key", api_key)

        self.config.set("agents.cache_ttl_seconds", self.cache_ttl_spin.value())
        self.config.set(
            "agents.enable_legal_reasoning", self.cb_legal_reasoning.isChecked()
        )
        self.config.set(
            "agents.enable_entity_extractor", self.cb_entity_extractor.isChecked()
        )
        self.config.set("agents.enable_irac", self.cb_irac.isChecked())
        self.config.set("agents.enable_toulmin", self.cb_toulmin.isChecked())
        self.config.set("agents.enable_registry", self.cb_registry.isChecked())

        self.config.set("vector.dimension", self.vec_dim_spin.value())
        self.config.set("vector.embedding_model", self.vec_model_edit.text().strip())
        self.config.set(
            "vector.use_sentence_transformers", self.cb_use_st.isChecked()
        )

        self.config.set("memory.approval_threshold", self.approval_spin.value())

        logger.info("Settings saved via dialog")
        self.accept()
