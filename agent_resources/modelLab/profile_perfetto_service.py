# https://github.com/google/perfetto/blob/master/tools/open_trace_in_ui

import argparse
import http.server
import os
import socketserver
import webbrowser
from modelLab import logger


# HTTP Server used to open the trace in the browser only once.
class HttpHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", self.server.allow_origin)
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_GET(self):
        if self.path != "/" + self.server.expected_fname:
            self.send_error(404, "File not found")
            return

        self.server.fname_get_completed = True
        super().do_GET()


def open_trace(path, origin):
    # We reuse the HTTP+RPC port because it's the only one allowed by the CSP.
    PORT = 9001
    logger.info(
        f"Opening trace file in {origin}. Please allow browser to access localhost:{PORT}"
    )

    path = os.path.abspath(path)
    os.chdir(os.path.dirname(path))
    fname = os.path.basename(path)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), HttpHandler) as httpd:
        address = f"{origin}/#!/?url=http://127.0.0.1:{PORT}/{fname}&referrer=aitk"
        webbrowser.open_new_tab(address)

        httpd.expected_fname = fname
        httpd.fname_get_completed = None
        httpd.allow_origin = origin
        while httpd.fname_get_completed is None:
            httpd.handle_request()
    logger.info("Perfetto trace file opened successfully.")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--file", type=str)
    parser.add_argument("--origin", default="https://ui.perfetto.dev")
    parser.add_argument("--runtime", help="runtime arg placeholder")

    args = parser.parse_args()
    open_trace(args.file, args.origin)


if __name__ == "__main__":
    main()
