import sys

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import PySide6.QtWidgets as _QtWidgets  # noqa: F401
    import PySide6.QtCore as _QtCore        # noqa: F401
    import PySide6.QtGui as _QtGui          # noqa: F401

from PySide6.QtWidgets import QApplication  # noqa: E402

from .memory_review_tab import MemoryReviewTab  # noqa: E402


def main():
    app = QApplication(sys.argv)
    w = MemoryReviewTab()
    w.setWindowTitle("Memory Review")
    w.resize(900, 500)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
