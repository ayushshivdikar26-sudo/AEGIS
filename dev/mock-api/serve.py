#!/usr/bin/env python3
"""
AEGIS Dev Mock API & Static File Server (serve.py)
Built with Python standard library only. Binds to 127.0.0.1:8000.
Enforces strict Content-Security-Policy and serves fixtures matching API contract v1 (Part 1 s10).
"""

import http.server
import json
import mimetypes
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

HOST = "127.0.0.1"
PORT = 8000

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = BASE_DIR / "Frontend"
FIXTURES_FILE = BASE_DIR / "dev" / "mock-api" / "fixtures" / "dataset.json"

STRICT_CSP = (
    "default-src 'self'; "
    "img-src 'self' data:; "
    "script-src 'self'; "
    "style-src 'self'; "
    "font-src 'self'; "
    "object-src 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


def load_dataset() -> dict:
    if not FIXTURES_FILE.exists():
        return {"extensions": []}
    with open(FIXTURES_FILE, encoding="utf-8") as f:
        return json.load(f)


class MockApiHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Clean logging format
        pass

    def send_security_headers(self, content_type: str = "application/json"):
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Security-Policy", STRICT_CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Request-ID", "mock-req-001")
        self.send_header("Access-Control-Allow-Origin", "null")  # No cross-origin
        self.end_headers()

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query = parse_qs(parsed_url.query)

        # 1. Handle artificial delay if ?delay= is provided
        if "delay" in query:
            try:
                ms = int(query["delay"][0])
                time.sleep(ms / 1000.0)
            except ValueError:
                pass

        # 2. Handle artificial forced failure if ?fail= is provided
        if "fail" in query:
            fail_target = query["fail"][0]
            if fail_target in path:
                self.send_response(500)
                self.send_security_headers()
                err_resp = {
                    "error": {
                        "code": "forced_failure",
                        "message": f"Simulated 500 error for section {fail_target}",
                        "request_id": "mock-fail-001",
                    }
                }
                self.wfile.write(json.dumps(err_resp).encode("utf-8"))
                return

        # 3. Route API endpoints
        if path.startswith("/api/"):
            self.handle_api(path, query)
            return

        # 4. Serve Static Frontend Files
        self.handle_static(path)

    def handle_api(self, path: str, query: dict):
        dataset = load_dataset()
        extensions = dataset.get("extensions", [])

        # Route: GET /api/extensions
        if path == "/api/extensions":
            self.send_response(200)
            self.send_security_headers()
            list_items = []
            for ext in extensions:
                list_items.append(
                    {
                        "id": ext["id"],
                        "name": ext["name"],
                        "browser": ext["browser"],
                        "version": ext["version"],
                        "icon_url": ext.get("icon_url"),
                        "risk_score": ext.get("assessment", {}).get("risk_score", 0),
                        "risk_level": ext.get("assessment", {}).get("risk_level", "low"),
                    }
                )
            resp = {"source": "fixture", "extensions": list_items}
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        # Pattern: /api/extensions/{id}
        m_ext = re.match(r"^/api/extensions/([^/]+)$", path)
        if m_ext:
            ext_id = unquote(m_ext.group(1))
            ext = next((e for e in extensions if e["id"] == ext_id), None)
            if not ext:
                self.send_response(404)
                self.send_security_headers()
                self.wfile.write(
                    json.dumps(
                        {
                            "error": {
                                "code": "not_found",
                                "message": "Extension not found",
                            }
                        }
                    ).encode("utf-8")
                )
                return
            self.send_response(200)
            self.send_security_headers()
            resp = {
                "id": ext["id"],
                "name": ext["name"],
                "browser": ext["browser"],
                "version": ext["version"],
                "icon_url": ext.get("icon_url"),
                "developer": ext.get("developer"),
                "description": ext.get("description", {"text": None, "origin": "unavailable"}),
                "capabilities": {"ai_analysis": False},
                "assessment": ext.get("assessment", {}),
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        # Pattern: /api/extensions/{id}/permissions
        m_perm = re.match(r"^/api/extensions/([^/]+)/permissions$", path)
        if m_perm:
            ext_id = unquote(m_perm.group(1))
            ext = next((e for e in extensions if e["id"] == ext_id), None)
            if not ext:
                self.send_response(404)
                self.send_security_headers()
                self.wfile.write(
                    json.dumps(
                        {
                            "error": {
                                "code": "not_found",
                                "message": "Extension not found",
                            }
                        }
                    ).encode("utf-8")
                )
                return
            self.send_response(200)
            self.send_security_headers()
            self.wfile.write(
                json.dumps(ext.get("permissions", {"api": [], "host": [], "optional": []})).encode("utf-8")
            )
            return

        # Pattern: /api/extensions/{id}/versions
        m_ver = re.match(r"^/api/extensions/([^/]+)/versions$", path)
        if m_ver:
            ext_id = unquote(m_ver.group(1))
            ext = next((e for e in extensions if e["id"] == ext_id), None)
            if not ext:
                self.send_response(404)
                self.send_security_headers()
                self.wfile.write(
                    json.dumps(
                        {
                            "error": {
                                "code": "not_found",
                                "message": "Extension not found",
                            }
                        }
                    ).encode("utf-8")
                )
                return
            self.send_response(200)
            self.send_security_headers()
            self.wfile.write(json.dumps({"versions": ext.get("versions", [])}).encode("utf-8"))
            return

        # Pattern: /api/extensions/{id}/compare?from=&to=
        m_comp = re.match(r"^/api/extensions/([^/]+)/compare$", path)
        if m_comp:
            ext_id = unquote(m_comp.group(1))
            ext = next((e for e in extensions if e["id"] == ext_id), None)
            if not ext:
                self.send_response(404)
                self.send_security_headers()
                self.wfile.write(
                    json.dumps(
                        {
                            "error": {
                                "code": "not_found",
                                "message": "Extension not found",
                            }
                        }
                    ).encode("utf-8")
                )
                return
            from_v = query.get("from", [""])[0]
            to_v = query.get("to", [""])[0]

            creep_data = ext.get("creep", {})
            self.send_response(200)
            self.send_security_headers()
            comp_resp = {
                "from": from_v or "1.0",
                "to": to_v or "2.0",
                "score_from": creep_data.get("score_from", 20),
                "score_to": creep_data.get("score_to", 70),
                "api": {
                    "added": [i for i in creep_data.get("added", []) if i.get("kind") == "api"],
                    "removed": [i for i in creep_data.get("removed", []) if i.get("kind") == "api"],
                    "retained": [{"name": "storage", "risk_label": "low"}],
                },
                "host": {
                    "added": [i for i in creep_data.get("added", []) if i.get("kind") == "host"],
                    "removed": [i for i in creep_data.get("removed", []) if i.get("kind") == "host"],
                    "retained": [],
                    "broadened": creep_data.get("broadened", []),
                },
                "optional": {"added": [], "removed": [], "retained": []},
            }
            self.wfile.write(json.dumps(comp_resp).encode("utf-8"))
            return

        # Pattern: /api/extensions/{id}/creep
        m_creep = re.match(r"^/api/extensions/([^/]+)/creep$", path)
        if m_creep:
            ext_id = unquote(m_creep.group(1))
            ext = next((e for e in extensions if e["id"] == ext_id), None)
            if not ext:
                self.send_response(404)
                self.send_security_headers()
                self.wfile.write(
                    json.dumps(
                        {
                            "error": {
                                "code": "not_found",
                                "message": "Extension not found",
                            }
                        }
                    ).encode("utf-8")
                )
                return
            self.send_response(200)
            self.send_security_headers()
            self.wfile.write(
                json.dumps(
                    ext.get(
                        "creep",
                        {"available": False, "reason": "baseline_not_available"},
                    )
                ).encode("utf-8")
            )
            return

        # Unmatched API path
        self.send_response(404)
        self.send_security_headers()
        self.wfile.write(json.dumps({"error": {"code": "not_found", "message": "Unknown endpoint"}}).encode("utf-8"))

    def handle_static(self, path: str):
        if path in ("", "/"):
            target_file = FRONTEND_DIR / "dashboard.html"
        else:
            # Prevent directory traversal
            clean_path = path.lstrip("/")
            target_file = (FRONTEND_DIR / clean_path).resolve()
            if not str(target_file).startswith(str(FRONTEND_DIR.resolve())):
                self.send_response(403)
                self.send_security_headers("text/plain")
                self.wfile.write(b"Forbidden")
                return

        if not target_file.exists() or not target_file.is_file():
            self.send_response(404)
            self.send_security_headers("text/plain")
            self.wfile.write(b"Not Found")
            return

        mime_type, _ = mimetypes.guess_type(str(target_file))
        if mime_type is None:
            mime_type = "application/octet-stream"
        if mime_type.startswith("text/") or mime_type in (
            "application/javascript",
            "image/svg+xml",
        ):
            mime_type += "; charset=utf-8"

        try:
            with open(target_file, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_security_headers(mime_type)
            self.wfile.write(content)
        except OSError as exc:
            self.send_response(500)
            self.send_security_headers("text/plain")
            self.wfile.write(f"Server Error: {exc}".encode())


def run_server():
    httpd = http.server.ThreadingHTTPServer((HOST, PORT), MockApiHandler)
    httpd.daemon_threads = True
    print(f"AEGIS Dev Mock Server running at http://{HOST}:{PORT}/", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.", flush=True)
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run_server()
