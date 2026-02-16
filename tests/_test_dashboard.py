"""Quick test: does the dashboard create without blocking?"""
import sys, os, time
os.environ.setdefault("QT_QPA_PLATFORM", "windows")
sys.path.insert(0, os.path.dirname(__file__))

from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)

from gui.gui_dashboard import LegalAIDashboard, AsyncioThread

at = AsyncioThread()
at.start()

print("Creating dashboard...", flush=True)
t0 = time.time()
try:
    d = LegalAIDashboard(at)
    elapsed = time.time() - t0
    print(f"Dashboard created in {elapsed:.2f}s", flush=True)
    d.show()
    print("Window shown OK", flush=True)
except Exception as e:
    print(f"ERROR: {e}", flush=True)
    import traceback; traceback.print_exc()

at.stop()
at.wait(2000)
print("Done.", flush=True)
