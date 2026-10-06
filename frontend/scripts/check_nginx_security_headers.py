#!/usr/bin/env python3
"""Exercise the shipped Nginx config over HTTP, including SPA redirects.

Run with Python 3 and nginx on PATH, or set NGINX_BINARY to its executable.
The temporary server binds only to localhost and does not alter system Nginx.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, build_opener


class NginxSecurityHeaders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary = os.environ.get("NGINX_BINARY") or shutil.which("nginx")
        if not cls.binary:
            raise RuntimeError("nginx is required; install it or set NGINX_BINARY")
        cls.temp = tempfile.TemporaryDirectory(prefix="isg-nginx-check-")
        cls.addClassCleanup(cls.temp.cleanup)
        base = Path(cls.temp.name)
        (base / "logs").mkdir()
        web = base / "html"
        (web / "assets").mkdir(parents=True)
        (web / "index.html").write_text("<!doctype html><title>ISG test</title>")
        (web / "assets" / "test.js").write_text("console.log('test');")
        (web / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        cls.url = f"http://127.0.0.1:{port}"
        # Replace only runtime paths/listener; header/location logic is unmodified.
        source = Path(__file__).resolve().parents[1] / "nginx.conf"
        server = source.read_text().replace(
            "listen 80;", f"listen 127.0.0.1:{port};"
        ).replace("/usr/share/nginx/html", str(web))
        config = base / "nginx.conf"
        user = "user root root;\n" if os.geteuid() == 0 else ""
        config.write_text(
            f"{user}master_process off;\npid {base}/nginx.pid;\nerror_log {base}/error.log;\n"
            f"events {{}}\nhttp {{ access_log off; {server} }}\n"
        )
        command = [cls.binary, "-p", str(base), "-c", str(config)]
        validation = subprocess.run(command + ["-t"], capture_output=True, text=True)
        if validation.returncode:
            raise RuntimeError(validation.stderr)
        cls.process = subprocess.Popen(command + ["-g", "daemon off;"])
        cls.addClassCleanup(cls.stop)
        cls.http = build_opener(ProxyHandler({}))
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if cls.process.poll() is not None:
                raise RuntimeError((base / "error.log").read_text())
            try:
                with cls.http.open(cls.url + "/robots.txt", timeout=0.2):
                    return
            except (URLError, TimeoutError):
                time.sleep(0.05)
        raise RuntimeError("temporary nginx did not become ready")

    @classmethod
    def stop(cls):
        cls.process.terminate()
        try:
            cls.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.process.kill()
            cls.process.wait(timeout=5)

    def response(self, path, status=200):
        try:
            response = self.http.open(self.url + path, timeout=3)
        except HTTPError as error:
            response = error
        with response:
            body = response.read()
            self.assertEqual(response.status, status)
            headers = response.headers
        expected = {
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(self), microphone=(self), geolocation=(self)",
            "Cross-Origin-Opener-Policy": "same-origin-allow-popups",
            "Cross-Origin-Resource-Policy": "same-site",
            "X-Permitted-Cross-Domain-Policies": "none",
        }
        for name, value in expected.items():
            self.assertEqual(headers.get_all(name), [value], (path, name))
        csp = headers.get_all("Content-Security-Policy")
        self.assertIsNotNone(csp, path)
        self.assertEqual(len(csp), 1, path)
        self.assertIn("frame-ancestors 'none'", csp[0])
        self.assertIn("script-src 'self' https://challenges.cloudflare.com", csp[0])
        self.assertIn("frame-src 'self' https://challenges.cloudflare.com", csp[0])
        return headers, body

    def html(self, path):
        headers, body = self.response(path)
        self.assertIn(b"<title>ISG test</title>", body)
        self.assertEqual(
            headers.get_all("Cache-Control"),
            ["no-store, no-cache, must-revalidate"],
        )

    def test_root(self):
        self.html("/")

    def test_index(self):
        self.html("/index.html")

    def test_spa_route(self):
        self.html("/firmalar/42?tab=egitim")

    def test_static_asset(self):
        headers, body = self.response("/assets/test.js")
        self.assertIn(b"console.log", body)
        self.assertIsNone(headers.get("Cache-Control"))

    def test_missing_asset(self):
        self.response("/assets/missing.js", status=404)

    def test_robots(self):
        self.response("/robots.txt")

    def test_missing_security_file(self):
        self.response("/.well-known/security.txt", status=404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
