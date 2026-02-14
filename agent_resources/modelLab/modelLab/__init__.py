import logging
import sys

logger = logging.getLogger(__name__)

if not logger.hasHandlers():
    logger.setLevel(logging.INFO)
    _sc = logging.StreamHandler(stream=sys.stdout)
    _sc.setLevel(logging.DEBUG)
    _sc.addFilter(lambda record: record.levelno < logging.ERROR)
    # JobLogger already has [%(asctime)s] [%(levelname)s]
    _formatter = logging.Formatter("[%(filename)s:%(lineno)d:%(funcName)s] %(message)s")
    _sc.setFormatter(_formatter)
    _sc.stream.reconfigure(encoding='utf-8')
    logger.addHandler(_sc)

    # Handler for ERROR, and CRITICAL to stderr
    _stderr_handler = logging.StreamHandler(stream=sys.stderr)
    _stderr_handler.setLevel(logging.ERROR)
    # because we only log message from stderr with error / Exception: in the line
    _formatter = logging.Formatter("[%(filename)s:%(lineno)d:%(funcName)s] Error: %(message)s")
    _stderr_handler.setFormatter(_formatter)
    _stderr_handler.stream.reconfigure(encoding='utf-8')
    logger.addHandler(_stderr_handler)

    logger.propagate = False


class ExitErrorCodes:
    # Profiling related
    ONNX_FILE_BAD_NAME = 100
    UNSUPPORTED_INPUT_TYPE = 101
    UNSUPPORTED_INITIALIZER_TYPE = 102
    # Install related
    INSTALL_WIN_APP_RUNTIME_CANCELLED = 201
    INSTALL_WIN_APP_RUNTIME_FAILED = 202
    # HF related
    HF_NOT_LOGGED_IN = 300


def register_execution_providers_to_onnxruntime():
    import subprocess
    import json
    from pathlib import Path
    import onnxruntime as ort
    
    worker_script = str(Path(__file__).parent / 'winml.py')
    result = subprocess.check_output([sys.executable, worker_script], text=True)
    paths = json.loads(result)

    for item in paths.items():
        try:
            print(f"----register ort ep---- {item[0]} {item[1]}")
            ort.register_execution_provider_library(item[0], item[1])
        except Exception as e:
            logger.warning(f"Failed to register execution providers: {e}")


def register_execution_providers_to_onnxruntime_genai():
    import subprocess
    import json
    from pathlib import Path
    import onnxruntime_genai as og
    
    worker_script = str(Path(__file__).parent / 'winml.py')
    result = subprocess.check_output([sys.executable, worker_script], text=True)
    paths = json.loads(result)
    for item in paths.items():
        try:
            print(f"----register ort genai ep---- {item[0]} {item[1]}")
            og.register_execution_provider_library(item[0], item[1])
        except Exception as e:
            logger.warning(f"Failed to register execution providers: {e}")
