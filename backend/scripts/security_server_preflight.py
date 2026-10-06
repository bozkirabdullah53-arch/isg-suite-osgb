#!/usr/bin/env python3
"""Read-only deployment evidence; no credentials, customer rows or changes.

Run on the hosting server with Python 3.8+; no application packages required.
The public checks use only GET, verify TLS, and never guess passwords/codes.
Exit 1 means a failed check; exit 2 means evidence is incomplete.
"""
import argparse
import configparser
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


def command(args, cwd=None):
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=15)
        return result.returncode, result.stdout + result.stderr
    except (OSError, subprocess.TimeoutExpired):
        return -1, ""


def result(name, status, detail):
    return {"check": name, "status": status, "detail": detail}


def local_checks(repo):
    checks = []
    code, output = command(["git", "rev-parse", "HEAD"], cwd=repo)
    sha = output.strip()
    checks.append(result("repository_commit", "INFO" if code == 0 else "CHECK",
                         sha if re.fullmatch(r"[0-9a-f]{40}", sha) else "unavailable"))
    code, output = command(["git", "status", "--porcelain"], cwd=repo)
    checks.append(result("repository_clean", "PASS" if code == 0 and not output.strip() else "CHECK",
                         "clean" if code == 0 and not output.strip() else "review local changes before deploy"))
    plesk = shutil.which("plesk")
    if plesk:
        code, output = command([plesk, "version"])
        match = re.search(r"\b18\.0\.\d+(?:\.\d+)?\b", output)
        version = match.group(0) if code == 0 and match else None
        update = re.search(r"Update\s*#\s*(\d+)", output, re.IGNORECASE)
        if version and len(version.split(".")) == 3 and update:
            version += "." + update.group(1)
        if version and len(version.split(".")) == 4:
            parts = tuple(map(int, version.split(".")))
            patched = parts >= (18, 0, 81, 1) or (parts[:3] == (18, 0, 80) and parts[3] >= 8)
            checks.append(result("plesk_cve_patch", "PASS" if patched else "FAIL", version))
        else:
            checks.append(result("plesk_cve_patch", "CHECK", version or "full version unavailable"))
        code, output = command([plesk, "bin", "extension", "--get-xml-info", "rest-api"])
        match = re.search(r"<module\b[^>]*?/>", output)
        try:
            version = ET.fromstring(match.group(0)).get("fullVersion") if code == 0 and match else None
            number = re.match(r"(\d+)\.(\d+)\.(\d+)", version or "")
            patched = number and tuple(map(int, number.groups())) >= (2, 4, 7)
            checks.append(result("plesk_rest_api_patch", "PASS" if patched else "FAIL" if number else "CHECK",
                                 version or "extension version unavailable"))
        except ET.ParseError:
            checks.append(result("plesk_rest_api_patch", "CHECK", "extension output not recognized"))
    else:
        checks.append(result("plesk_cve_patch", "CHECK", "Plesk CLI unavailable or not permitted"))
        checks.append(result("plesk_rest_api_patch", "CHECK", "Plesk CLI unavailable or not permitted"))
    config = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        read = config.read("/usr/local/psa/admin/conf/panel.ini")
        enabled = config.get("api", "enabled", fallback="unset").strip().lower()
        restricted = bool(config.get("api", "allowedIPs", fallback="").strip())
        protected = enabled in {"off", "false", "0"} or restricted
        checks.append(result("plesk_api_config", "INFO" if protected else "CHECK",
                             "disabled or IP restriction configured; external retest still required"
                             if protected else "API restriction not demonstrated" if read else "panel.ini unavailable"))
    except (OSError, configparser.Error):
        checks.append(result("plesk_api_config", "CHECK", "panel.ini unavailable"))
    checks.append(result("panel_firewall", "CHECK", "verify TCP 8443 from an unauthorized external source"))
    return checks


def get(url):
    try:
        request = Request(url, headers={"User-Agent": "ISG-Suite-ReadOnly-Security-Preflight/1.0"})
        try:
            response = urlopen(request, timeout=12)
        except HTTPError as error:
            response = error
        with response:
            return response.status, response.headers, response.read(65536), response.geturl()
    except (URLError, OSError, TimeoutError):
        return 0, {}, b"", url


def public_checks(origin):
    checks = []
    for path in ("/", "/api/v1/live", "/health", "/api/v1/openapi.json"):
        status, headers, body, final_url = get(origin + path)
        if status == 0 or status >= 500:
            checks.append(result(path, "CHECK", "TLS/network/origin error; not proof of access control"))
            continue
        if urlsplit(final_url).scheme != "https" or urlsplit(final_url).netloc != urlsplit(origin).netloc:
            checks.append(result(path, "CHECK", "redirected to a different origin; verify deployment target"))
            continue
        if path == "/":
            if status != 200:
                checks.append(result(path, "FAIL", "homepage does not return 200"))
                continue
            expected = {
                "X-Frame-Options": "DENY", "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "strict-origin-when-cross-origin",
                "Cross-Origin-Resource-Policy": "same-site",
            }
            missing = [key for key, value in expected.items() if headers.get(key) != value]
            for key in ("Strict-Transport-Security", "Content-Security-Policy", "Permissions-Policy"):
                if not headers.get(key):
                    missing.append(key)
            checks.append(result("homepage_security_headers", "FAIL" if missing else "PASS",
                                 "missing or unexpected: " + ", ".join(missing) if missing else "required headers present"))
            csp = headers.get("Content-Security-Policy", "")
            turnstile = all(re.search(r"(?:^|;)\s*" + directive + r"[^;]*https://challenges\.cloudflare\.com(?:\s|;|$)", csp)
                            for directive in ("script-src", "frame-src"))
            checks.append(result("turnstile_csp", "PASS" if turnstile else "FAIL",
                                 "script/frame allowed" if turnstile else "review CSP before enabling CAPTCHA"))
        elif path == "/api/v1/live":
            passed = status == 204 and not body and "no-store" in headers.get("Cache-Control", "")
            checks.append(result(path, "PASS" if passed else "FAIL", "HTTP " + str(status)))
        elif path == "/health":
            checks.append(result("health_authentication", "PASS" if status in (401, 403) else "FAIL",
                                 "anonymous HTTP " + str(status)))
        else:
            checks.append(result("application_schema", "PASS" if status in (401, 403, 404, 410) else "FAIL",
                                 "HTTP " + str(status) + "; requires denied/missing schema, not SPA HTML"))
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("/opt/isg-suite-osgb"))
    parser.add_argument("--origin", default="https://www.isgsuite.com.tr")
    parser.add_argument("--public-only", action="store_true")
    args = parser.parse_args()
    parsed = urlsplit(args.origin)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        parser.error("origin must be an HTTPS origin without credentials or path")
    origin = args.origin.rstrip("/")
    checks = [] if args.public_only else local_checks(args.repo)
    checks.extend(public_checks(origin))
    report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "origin": origin,
              "read_only": True, "checks": checks,
              "scope": "deployment preflight; not authenticated tenant retest or external pentest closure"}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if any(item["status"] == "FAIL" for item in checks) else 2 if any(item["status"] == "CHECK" for item in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
