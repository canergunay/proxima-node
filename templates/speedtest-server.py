#!/usr/bin/env python3
"""
Proxima Speed Test Server — standalone HTTPS server for measuring tunnel throughput.

Endpoints:
  HEAD /speedtest/ping            — latency measurement (empty 200)
  GET  /speedtest/download?size=N — download N MB of data (default 1, max 50)
  POST /speedtest/upload          — upload test, reads+discards body, returns byte count
  GET  /speedtest/health          — health check (no auth required)

Environment:
  SPEEDTEST_API_KEY  — required, Bearer token for authentication
  SPEEDTEST_PORT     — optional, default 8999
  SPEEDTEST_CERT     — optional, default /opt/proxima-speedtest/cert.pem
  SPEEDTEST_KEY      — optional, default /opt/proxima-speedtest/key.pem
"""

import os
import ssl
import sys
import time
import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs

API_KEY = os.environ.get("SPEEDTEST_API_KEY", "")
PORT = int(os.environ.get("SPEEDTEST_PORT", "8999"))
VERSION = "1.0.0"
MAX_DOWNLOAD_MB = 50
MAX_UPLOAD_MB = 100
DOWNLOAD_CHUNK = b"\x00" * (64 * 1024)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("speedtest")


class SpeedTestHandler(BaseHTTPRequestHandler):
    server_version = f"ProximaSpeedTest/{VERSION}"
    disable_nagle_algorithm = True

    def log_message(self, fmt, *args):
        log.info(f"{self.client_address[0]} - {fmt % args}")

    def _check_auth(self) -> bool:
        if not API_KEY:
            self._error(500, "Server API key not configured")
            return False
        auth = self.headers.get("Authorization", "")
        if auth != f"Bearer {API_KEY}":
            self._error(401, "Unauthorized")
            return False
        return True

    def _error(self, code: int, message: str):
        body = json.dumps({"error": message}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data: dict, code: int = 200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _parse_path(self):
        parsed = urlparse(self.path)
        return parsed.path, parse_qs(parsed.query)

    def do_HEAD(self):
        path, _ = self._parse_path()
        if path == "/speedtest/ping":
            if not self._check_auth():
                return
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.send_header("X-Server-Time", str(int(time.time())))
            self.end_headers()
        else:
            self._error(404, "Not found")

    def do_GET(self):
        path, params = self._parse_path()
        if path == "/speedtest/health":
            self._json({"ok": True, "version": VERSION, "time": int(time.time())})
            return
        if path == "/speedtest/download":
            if not self._check_auth():
                return
            size_mb = int(params.get("size", ["1"])[0])
            if size_mb < 1:
                size_mb = 1
            if size_mb > MAX_DOWNLOAD_MB:
                self._error(400, f"Max download size is {MAX_DOWNLOAD_MB} MB")
                return
            total_bytes = size_mb * 1024 * 1024
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(total_bytes))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            sent = 0
            try:
                while sent < total_bytes:
                    chunk_size = min(len(DOWNLOAD_CHUNK), total_bytes - sent)
                    self.wfile.write(DOWNLOAD_CHUNK[:chunk_size])
                    self.wfile.flush()
                    sent += chunk_size
            except (BrokenPipeError, ConnectionResetError):
                log.warning(f"Client disconnected during download ({sent}/{total_bytes})")
            return
        self._error(404, "Not found")

    def do_POST(self):
        path, _ = self._parse_path()
        if path == "/speedtest/upload":
            if not self._check_auth():
                return
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > MAX_UPLOAD_MB * 1024 * 1024:
                self._error(400, f"Max upload size is {MAX_UPLOAD_MB} MB")
                return
            received = 0
            buf_size = 1024 * 1024
            try:
                while received < content_length:
                    chunk = self.rfile.read(min(buf_size, content_length - received))
                    if not chunk:
                        break
                    received += len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                log.warning(f"Client disconnected during upload ({received}/{content_length})")
            self._json({"received_bytes": received})
            return
        self._error(404, "Not found")


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    if not API_KEY:
        log.error("SPEEDTEST_API_KEY environment variable is required")
        sys.exit(1)
    cert = os.environ.get("SPEEDTEST_CERT", "/opt/proxima-speedtest/cert.pem")
    key = os.environ.get("SPEEDTEST_KEY", "/opt/proxima-speedtest/key.pem")
    server = ThreadedHTTPServer(("0.0.0.0", PORT), SpeedTestHandler)
    if os.path.exists(cert) and os.path.exists(key):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        log.info(f"Proxima Speed Test Server v{VERSION} listening on https://0.0.0.0:{PORT}")
    else:
        log.info(f"Proxima Speed Test Server v{VERSION} listening on http://0.0.0.0:{PORT}")
        log.warning("No TLS cert found, running without HTTPS")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
