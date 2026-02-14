import subprocess
import sys
import time
import requests
import argparse
import threading
from pathlib import Path

GRADIO_HOST = "127.0.0.1"
GRADIO_PORT = 7860
GRADIO_URL = f"http://{GRADIO_HOST}:{GRADIO_PORT}"

# Shared buffer to capture stderr for error reporting
stderr_lines = []


def drain_pipe_to_buffer(pipe, buffer):
    """Drain a pipe in a background thread, storing lines in buffer for later use"""
    try:
        for line in pipe:
            buffer.append(line)
    except:
        pass


def await_and_test_gradio_proc(server_proc, gradio_sample_path):
    start = time.time()
    error_log = ""
    timeout = 120

    server_ready = False
    while time.time() - start < timeout:
        if server_proc.poll() is not None:
            if server_proc.stderr:
                error_log = server_proc.stderr.read()
            else:
                error_log = "Server process exited unexpectedly"
            return False, error_log
        try:
            r = requests.get(GRADIO_URL, timeout=1)
            if r.status_code == 200:
                server_ready = True
                break
        except requests.RequestException:
            pass
        time.sleep(0.5)

    if not server_ready:
        return (
            False,
            f"Server timeout - server did not become ready within {timeout} seconds",
        )
    elif gradio_sample_path is None:
        return True, ""
    else:
        try:
            client_timeout = 120
            client_proc = subprocess.Popen(
                [sys.executable, str(gradio_sample_path), "--client"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = client_proc.communicate(timeout=client_timeout)
            if client_proc.returncode == 0:
                return True, ""
            else:
                return False, f"Client Error:\nstdout: {stdout}\nstderr: {stderr}"

        except subprocess.TimeoutExpired:
            client_proc.kill()
            client_proc.communicate()  # Clean up
            return (
                False,
                f"Client timeout - client request did not complete within {client_timeout} seconds",
            )
        except Exception as e:
            return False, f"Client Error:\nFailed to start client process: {str(e)}"


def run_and_check_gradio_sample(gradio_sample_path):
    global stderr_lines
    stderr_lines = []  # Reset buffer for each run

    server_proc = subprocess.Popen(
        [sys.executable, str(gradio_sample_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # FIX: Drain stdout and stderr in background threads to prevent buffer blocking
    # This is critical for models that produce lots of log output (e.g., VitisAI NPU)
    # We capture stderr into a buffer so we can report it if the test fails
    stdout_lines = []
    stdout_thread = threading.Thread(target=drain_pipe_to_buffer, args=(server_proc.stdout, stdout_lines), daemon=True)
    stderr_thread = threading.Thread(target=drain_pipe_to_buffer, args=(server_proc.stderr, stderr_lines), daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    success, error_log = await_and_test_gradio_proc(
        server_proc, gradio_sample_path=gradio_sample_path
    )

    # If failed, append captured stderr to error log
    if not success and stderr_lines:
        captured_stderr = "".join(stderr_lines[-100:])  # Last 100 lines to avoid huge output
        error_log = f"{error_log}\n\nCaptured stderr (last 100 lines):\n{captured_stderr}"

    try:
        server_proc.terminate()
        server_proc.wait(timeout=5)
    except Exception:
        server_proc.kill()

    return success, error_log


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Gradio sample application")
    parser.add_argument(
        "sample_path", type=str, help="Path to the Gradio sample Python file"
    )
    args = parser.parse_args()

    gradio_sample_path = Path(args.sample_path)
    success, error_log = run_and_check_gradio_sample(gradio_sample_path)
    if success:
        print("Gradio sample test passed successfully.")
        sys.exit(0)
    else:
        print(f"Gradio sample test failed:\n{error_log}")
        sys.exit(1)
