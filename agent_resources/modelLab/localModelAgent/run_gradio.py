import argparse
import subprocess
import sys
import os
from pathlib import Path
import time
import requests
import threading

GRADIO_HOST = "127.0.0.1"
GRADIO_PORT = 7860
GRADIO_URL = f"http://{GRADIO_HOST}:{GRADIO_PORT}"

# Shared buffers to capture output for error reporting
stdout_lines = []
stderr_lines = []


def drain_pipe_to_buffer(pipe, buffer):
    """Drain a pipe in a background thread, storing lines in buffer for later use"""
    try:
        for line in pipe:
            buffer.append(line)
    except:
        pass


def await_gradio_server(proc, timeout: int = 120) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        # Check if process has exited
        if proc.poll() is not None:
            return False
        try:
            r = requests.get(GRADIO_URL, timeout=1)
            if r.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.5)
    return False


def run_gradio_detached(script_path: Path):
    global stdout_lines, stderr_lines
    stdout_lines = []
    stderr_lines = []

    print(f"Launching Gradio sample: {script_path}. It may take a while...")

    creationflags = 0
    preexec_fn = None
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        preexec_fn = os.setpgrp

    proc = subprocess.Popen(
        [sys.executable, str(script_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        close_fds=True,
        creationflags=creationflags,
        preexec_fn=preexec_fn,
    )

    # FIX: Drain stdout and stderr in background threads to prevent buffer blocking
    # This is critical for models that produce lots of log output (e.g., VitisAI NPU)
    stdout_thread = threading.Thread(target=drain_pipe_to_buffer, args=(proc.stdout, stdout_lines), daemon=True)
    stderr_thread = threading.Thread(target=drain_pipe_to_buffer, args=(proc.stderr, stderr_lines), daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    server_ok = await_gradio_server(proc)
    if server_ok:
        print("Gradio sample started successfully.")
        sys.exit(0)
    else:
        # Give threads a moment to finish capturing output
        time.sleep(0.5)

        # Use captured output from buffers
        stdout = "".join(stdout_lines[-100:]) if stdout_lines else ""
        stderr = "".join(stderr_lines[-100:]) if stderr_lines else ""

        # Try to clean up the process
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except:
            proc.kill()

        print("Gradio sample failed to start.")
        print("stdout:", stdout)
        print("stderr:", stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Launch a Gradio sample script in detached mode."
    )
    parser.add_argument(
        "--script_path", type=str, required=True, help="Path to the Gradio sample .py script."
    )
    parser.add_argument(
        "--runtime", type=str, help="Runtime environment (not used in this script)."
    )
    args = parser.parse_args()

    script_path = Path(args.script_path)
    run_gradio_detached(script_path)


if __name__ == "__main__":
    main()
