#!/usr/bin/env python3
"""
ssconf HTTPS server — serves Outline SS access config as JSON.
Proxima clients fetch this URL to auto-configure Shadowsocks.

Tokens and config are injected via environment variables at install time.
"""
import json, ssl, os, http.server

TOKEN = os.environ.get("SSCONF_TOKEN", "")
SERVER_IP = os.environ.get("SSCONF_SERVER_IP", "")
SS_PORT = int(os.environ.get("SSCONF_SS_PORT", "8388"))
SS_PASSWORD = os.environ.get("SSCONF_SS_PASSWORD", "")
SS_CIPHER = os.environ.get("SSCONF_SS_CIPHER", "chacha20-ietf-poly1305")
SS_PREFIX = os.environ.get("SSCONF_SS_PREFIX", "")
CERT_FILE = os.environ.get("SSCONF_CERT", "/opt/outline-ss/cert.pem")
KEY_FILE = os.environ.get("SSCONF_KEY", "/opt/outline-ss/key.pem")
PORT = int(os.environ.get("SSCONF_PORT", "8390"))


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == f"/{TOKEN}":
            config = {
                "server": SERVER_IP,
                "server_port": SS_PORT,
                "password": SS_PASSWORD,
                "method": SS_CIPHER,
            }
            if SS_PREFIX:
                config["prefix"] = SS_PREFIX
            data = json.dumps(config).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        pass


def main():
    if not TOKEN:
        print("ERROR: SSCONF_TOKEN not set", flush=True)
        return
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT_FILE, KEY_FILE)
    server = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    print(f"ssconf server listening on :{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
