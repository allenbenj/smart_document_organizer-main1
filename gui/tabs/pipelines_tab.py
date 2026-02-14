"""
Pipelines Tab - GUI component for pipeline execution

This module provides the UI for running document processing pipelines
with various presets and override options.
"""

import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .status_presenter import TabStatusPresenter
from ..ui import JobStatusWidget, ResultsSummaryBox

try:
    import requests
except ImportError:
    requests = None  # type: ignore

from ..services import api_client


class PipelinesTab(QWidget):
    def __init__(self):
        super().__init__()
        self.presets = []
        self.init_ui()
        self.load_presets()

    def init_ui(self):
        layout = QVBoxLayout()
        title = QLabel("Pipelines")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        controls = QGroupBox("Run Preset")
        c_layout = QVBoxLayout()
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        row1.addWidget(self.preset_combo)
        self.refresh_btn = QPushButton("Refresh")
        row1.addWidget(self.refresh_btn)
        c_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Document Path:"))
        self.path_edit = QLineEdit()
        row2.addWidget(self.path_edit)
        self.browse_btn = QPushButton("Browse")
        row2.addWidget(self.browse_btn)
        c_layout.addLayout(row2)

        # Override options
        override_group = QGroupBox("Overrides (optional)")
        og_layout = QVBoxLayout()
        # Persona for expert prompt
        pr_row = QHBoxLayout()
        pr_row.addWidget(QLabel("Persona:"))
        self.ov_persona = QComboBox()
        self.ov_persona.addItems(
            [
                "Lex _Legal Researcher_",
                "Ava _Legal Writer_",
                "Max _Detail Analyst_",
                "Aria _Appellate Specialist_",
            ]
        )
        pr_row.addWidget(self.ov_persona)
        og_layout.addLayout(pr_row)
        # Extractor options
        ex_row = QHBoxLayout()
        ex_row.addWidget(QLabel("Extractor:"))
        self.ov_extractor = QComboBox()
        self.ov_extractor.addItems(["Advanced", "Hybrid", "GLiNER", "Keyword"])
        ex_row.addWidget(self.ov_extractor)
        ex_row.addWidget(QLabel("Min Conf:"))
        self.ov_conf = QSlider(Qt.Orientation.Horizontal)
        self.ov_conf.setRange(0, 100)
        self.ov_conf.setValue(70)
        ex_row.addWidget(self.ov_conf)
        ex_row.addWidget(QLabel("Lang:"))
        self.ov_lang = QComboBox()
        self.ov_lang.addItems(["en", "es", "fr"])
        ex_row.addWidget(self.ov_lang)
        og_layout.addLayout(ex_row)
        # GLiNER model row
        gm_row = QHBoxLayout()
        gm_row.addWidget(QLabel("GLiNER Model:"))
        self.ov_gliner_model = QComboBox()
        self.ov_gliner_model.addItems(
            ["urchade/gliner_base", "urchade/gliner_large-v2.1"]
        )
        gm_row.addWidget(self.ov_gliner_model)
        og_layout.addLayout(gm_row)
        # Classifier/Embedding
        ce_row = QHBoxLayout()
        ce_row.addWidget(QLabel("Classifier:"))
        self.ov_cls_model = QComboBox()
        self.ov_cls_model.addItems(
            [
                "typeform/distilbert-base-uncased-mnli",
                "roberta-large-mnli",
                "facebook/bart-large-mnli",
                "MoritzLaurer/deberta-v3-large-zeroshot-v2",
            ]
        )
        ce_row.addWidget(self.ov_cls_model)
        ce_row.addWidget(QLabel("Embed:"))
        self.ov_emb_model = QComboBox()
        self.ov_emb_model.addItems(
            [
                "sentence-transformers/all-MiniLM-L6-v2",
                "sentence-transformers/all-mpnet-base-v2",
                "intfloat/e5-base-v2",
                "intfloat/e5-large-v2",
            ]
        )
        ce_row.addWidget(self.ov_emb_model)
        og_layout.addLayout(ce_row)
        override_group.setLayout(og_layout)
        c_layout.addWidget(override_group)

        row3 = QHBoxLayout()
        self.run_btn = QPushButton("Run Pipeline")
        row3.addWidget(self.run_btn)
        c_layout.addLayout(row3)
        controls.setLayout(c_layout)

        results = QGroupBox("Results")
        r_layout = QVBoxLayout()
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMinimumHeight(250)
        r_layout.addWidget(self.results_text)
        results.setLayout(r_layout)

        self.status_label = QLabel("Ready")
        self.status = TabStatusPresenter(self, self.status_label, source="Pipelines")
        self.job_status = JobStatusWidget("Pipeline Job")
        self.results_summary = ResultsSummaryBox()

        layout.addWidget(controls)
        layout.addWidget(self.status_label)
        layout.addWidget(self.job_status)
        layout.addWidget(self.results_summary)
        layout.addWidget(results)
        self.setLayout(layout)

        self.refresh_btn.clicked.connect(self.load_presets)
        self.browse_btn.clicked.connect(self.browse_path)
        self.run_btn.clicked.connect(self.run_pipeline)

    def load_presets(self):
        try:
            if not requests:
                raise RuntimeError("requests not available")
            r = requests.get(f"{api_client.base_url}/api/pipeline/presets", timeout=10)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text}")
            data = r.json().get("items", [])
            self.presets = data
            self.preset_combo.clear()
            for p in data:
                self.preset_combo.addItem(p.get("name", "Preset"))
        except Exception as e:
            self.results_text.setPlainText(f"Failed to load presets: {e}")
            self.status.error(f"Failed to load presets: {e}")

    def current_preset(self) -> dict:
        idx = self.preset_combo.currentIndex()
        if 0 <= idx < len(self.presets):
            return self.presets[idx]
        return {}

    def browse_path(self):
        fp, _ = QFileDialog.getOpenFileName(
            self, "Select Document", "", "All Files (*)"
        )
        if fp:
            self.path_edit.setText(fp)

    def run_pipeline(self):  # noqa: C901
        preset = self.current_preset()
        if not preset:
            self.status.warn("No preset selected.")
            return
        path = self.path_edit.text().strip()
        # Overlay overrides into a copy of preset steps
        steps = list(preset.get("steps", []))
        # Extractor override
        for s in steps:
            if s.get("name") == "extract_entities":
                opts = s.get("options", {})
                opts.update(
                    {
                        "extractor": (self.ov_extractor.currentText() or "").lower(),
                        "min_con": self.ov_conf.value() / 100.0,
                        "lang": self.ov_lang.currentText(),
                    }
                )
                if (self.ov_extractor.currentText() or "").lower() == "gliner":
                    opts["gliner_model"] = self.ov_gliner_model.currentText()
                s["options"] = opts
            if s.get("name") == "expert_prompt":
                opts = s.get("options", {})
                opts.update({"agent_name": self.ov_persona.currentText()})
                s["options"] = opts
            if s.get("name") == "classify":
                opts = s.get("options", {})
                opts.update(
                    {
                        "model_name": self.ov_cls_model.currentText(),
                        "quality_gate": True,
                    }
                )
                s["options"] = opts
            if s.get("name") == "embed_index":
                opts = s.get("options", {})
                opts.update({"model": self.ov_emb_model.currentText()})
                s["options"] = opts
        if getattr(self, "_worker", None) is not None and self._worker.isRunning():
            self.status.warn("Pipeline already running. Please wait for completion.")
            return

        modified = dict(preset)
        modified["steps"] = steps
        self.results_text.setPlainText("Running pipeline...")
        self.job_status.set_status("running", "Executing preset pipeline")
        self.status.loading("Running pipeline...")
        worker = PipelineRunnerWorker(modified, path)
        worker.finished_ok.connect(self.on_pipeline_ok)
        worker.finished_err.connect(self.on_pipeline_err)
        worker.start()
        self._worker = worker

    def on_pipeline_ok(self, result: dict):
        try:
            # Display a compact summary
            summary = {
                "success": result.get("success"),
                "keys": list((result.get("result") or {}).keys()),
            }
            self.results_text.setPlainText(json.dumps(summary, indent=2))
            self.job_status.set_status("success", "Pipeline run complete")
            self.results_summary.set_summary(
                "Pipeline completed successfully",
                "Displayed in Results panel",
                "Run Console",
            )
            self.status.success("Pipeline run complete")
        except Exception as e:  # noqa: F841
            self.results_text.setPlainText(str(result))
            self.job_status.set_status("success", "Pipeline run complete")
            self.results_summary.set_summary(
                "Pipeline completed",
                "Displayed in Results panel",
                "Run Console",
            )
            self.status.success("Pipeline run complete")

    def on_pipeline_err(self, err: str):
        self.results_text.setPlainText(f"Error: {err}")
        self.job_status.set_status("failed", "Pipeline failed")
        self.results_summary.set_summary(
            f"Pipeline failed: {err}",
            "No output generated",
            "Run Console",
        )
        self.status.error(f"Pipeline error: {err}")


# Import here to avoid circular imports
from .workers import PipelineRunnerWorker