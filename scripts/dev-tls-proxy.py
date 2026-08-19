#!/usr/bin/env python3
"""Best-effort local HTTPS front door for Anvil, for testing `gh` CLI.

Why this exists: `gh` (like other GitHub Enterprise Server-aware clients)
refuses to speak plain HTTP to any host other than github.com -- it always
requests `https://`. Anvil itself only speaks plain HTTP (that's Shotgun's
proxy, unchanged here). This script self-signs a cert with `openssl` and
terminates TLS in front of the real (HTTP) Anvil listener, purely for local
testing.

Usage:
    ./scripts/dev-tls-proxy.py --backend 127.0.0.1:3000 --listen 127.0.0.1:8443

Then:
    GH_HOST=127.0.0.1:8443 GH_TOKEN=<forgejo-token> \\
      SSL_CERT_FILE=/tmp/anvil-dev-cert/cert.pem gh api repos/OWNER/REPO

Trust caveat: Go's crypto/x509 respects SSL_CERT_FILE on Linux. On macOS,
Go uses the system Keychain and ignores SSL_CERT_FILE by default -- you'll
need to add /tmp/anvil-dev-cert/cert.pem to Keychain (or trust it via
`security add-trusted-cert`) for `gh` to accept it there. curl/httpie work
everywhere via `--cacert`. This is a local dev convenience only -- real
deployments belong behind a real reverse proxy (Caddy, nginx, a tunnel)
with a real certificate.
"""
import argparse
import http.client
import os
import ssl
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def ensure_cert(cert_dir):
    os.makedirs(cert_dir, exist_ok=True)
    cert = os.path.join(cert_dir, "cert.pem")
    key = os.path.join(cert_dir, "key.pem")
    if os.path.exists(cert) and os.path.exists(key):
        return cert, key
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", key, "-out", cert, "-days", "30", "-nodes",
            "-subj", "/CN=localhost",
            "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return cert, key


def make_handler(backend_host, backend_port):
    class ProxyHandler(BaseHTTPRequestHandler):
        def _proxy(self):
            body_len = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(body_len) if body_len else None
            conn = http.client.HTTPConnection(backend_host, backend_port, timeout=30)
            headers = {k: v for k, v in self.headers.items() if k.lower() != "host"}
            conn.request(self.command, self.path, body=body, headers=headers)
            resp = conn.getresponse()
            self.send_response(resp.status)
            for k, v in resp.getheaders():
                if k.lower() in ("transfer-encoding", "connection"):
                    continue
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(resp.read())
            conn.close()

        def do_GET(self):
            self._proxy()

        def do_POST(self):
            self._proxy()

        def do_PUT(self):
            self._proxy()

        def do_PATCH(self):
            self._proxy()

        def do_DELETE(self):
            self._proxy()

        def log_message(self, fmt, *args):
            sys.stderr.write("dev-tls-proxy: " + (fmt % args) + "\n")

    return ProxyHandler


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--backend", default="127.0.0.1:3000", help="Anvil's plain-HTTP address")
    p.add_argument("--listen", default="127.0.0.1:8443", help="Address to serve HTTPS on")
    p.add_argument("--cert-dir", default=os.path.join(tempfile.gettempdir(), "anvil-dev-cert"))
    args = p.parse_args()

    backend_host, backend_port = args.backend.rsplit(":", 1)
    listen_host, listen_port = args.listen.rsplit(":", 1)

    cert, key = ensure_cert(args.cert_dir)
    print(f"dev-tls-proxy: cert at {cert} (trust it, or use curl --cacert {cert})")

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)

    httpd = ThreadingHTTPServer((listen_host, int(listen_port)), make_handler(backend_host, int(backend_port)))
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    print(f"dev-tls-proxy: https://{args.listen} -> http://{args.backend}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
