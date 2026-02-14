from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import PySide6.QtWidgets as _QtWidgets  # noqa: F401
    import PySide6.QtCore as _QtCore        # noqa: F401
    import PySide6.QtGui as _QtGui          # noqa: F401

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    import requests  # noqa: E402
except Exception:
    requests = None


API_BASE = "http://127.0.0.1:8000/api"


class ViolationsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        title = QLabel("Violation Review")
        layout.addWidget(title)

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText(
            "Enter text to analyze for potential violations..."
        )
        layout.addWidget(self.text_input)

        btns = QHBoxLayout()
        load_btn = QPushButton("Load File")
        run_btn = QPushButton("Analyze")
        load_btn.clicked.connect(self.load_file)
        run_btn.clicked.connect(self.run)
        btns.addWidget(load_btn)
        btns.addWidget(run_btn)
        layout.addLayout(btns)

        self.result = QTextEdit()
        self.result.setReadOnly(True)
        layout.addWidget(self.result)

        self.setLayout(layout)

    def load_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Text File", "", "Text Files (*.txt);;All Files (*)"
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.text_input.setPlainText(f.read())
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def run(self):  # noqa: C901
        try:
            txt = self.text_input.toPlainText().strip()
            if not txt:
                QMessageBox.information(self, "Info", "Please enter text first")
                return
            if requests is None:
                QMessageBox.critical(self, "Error", "requests module not available")
                return
            r = requests.post(
                API_BASE + "/agents/violations", json={"text": txt}, timeout=15
            )
            self.result.setPlainText(r.text)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
