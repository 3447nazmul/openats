"""
Lightweight, Zero-Dependency HTTP Server for OpenATS.
Delivers the Linear-grade Dashboard UI, REST APIs, and Automatic Update Checker.
Hardened with ThreadingHTTPServer, 5 MB POST limit, strict localhost CORS, and security headers.
Author: Nazmul (@3447nazmul) - https://github.com/3447nazmul/openats
"""
import os
import json
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from . import __version__, __author__, __repository__
from .engine import analyze_ats_match
from .format_audit import audit_text_format
from .star_enhancer import analyze_bullet_point
from .updater import check_for_updates

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Maximum POST body size: 5 MB
MAX_POST_BODY_BYTES: int = 5 * 1024 * 1024

# Restrictive Content-Security-Policy for the served dashboard page
DASHBOARD_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com blob:; "
    "worker-src 'self' https://cdnjs.cloudflare.com blob:; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com data:; "
    "img-src 'self' data:; "
    "connect-src 'self' https://cdnjs.cloudflare.com; "
    "object-src 'none'; "
    "base-uri 'self'"
)


class OpenATSRequestHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests for OpenATS Web Dashboard and REST APIs."""

    def log_message(self, format, *args):
        # Quiet clean logging
        pass

    def _get_allowed_origin(self) -> str:
        """
        Return the request Origin if and only if it matches the local server's
        http://127.0.0.1:<PORT> or http://localhost:<PORT> origin. Never returns '*'.
        """
        origin = self.headers.get("Origin", "")
        if not origin:
            return ""
        server_port = getattr(self.server, "server_port", 8080)
        allowed = {
            f"http://127.0.0.1:{server_port}",
            f"http://localhost:{server_port}",
        }
        return origin if origin in allowed else ""

    def _send_security_and_cors_headers(self, is_html: bool = False):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if is_html:
            self.send_header("Content-Security-Policy", DASHBOARD_CSP)

        allowed_origin = self._get_allowed_origin()
        if allowed_origin:
            self.send_header("Access-Control-Allow-Origin", allowed_origin)
            self.send_header("Vary", "Origin")

    def send_json_response(self, status_code: int, data: dict):
        response_body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_body)))
        self._send_security_and_cors_headers(is_html=False)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(response_body)

    def do_OPTIONS(self):
        """Handle CORS pre-flight requests."""
        self.send_response(204)
        self._send_security_and_cors_headers(is_html=False)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        """Serves the Dashboard UI and static endpoints (ignoring query strings)."""
        route_path = urllib.parse.urlsplit(self.path).path

        if route_path in ("/", "/index.html"):
            index_path = os.path.join(TEMPLATES_DIR, "index.html")
            if not os.path.exists(index_path):
                # Fallback to root index.html if running from package root
                index_path = os.path.join(BASE_DIR, "..", "index.html")
            if not os.path.exists(index_path):
                self.send_json_response(404, {"error": "Dashboard template not found."})
                return
            with open(index_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self._send_security_and_cors_headers(is_html=True)
            self.end_headers()
            self.wfile.write(content)
        elif route_path == "/api/health":
            self.send_json_response(200, {
                "status": "ok",
                "app": "OpenATS",
                "version": __version__,
                "author": __author__,
                "repository": __repository__
            })
        elif route_path == "/api/check-update":
            update_info = check_for_updates(__version__, use_cache=True)
            self.send_json_response(200, update_info)
        else:
            self.send_json_response(404, {"error": "Not Found"})

    def do_POST(self):
        """Handles analysis and bullet enhancement requests with a 5 MB body size limit."""
        route_path = urllib.parse.urlsplit(self.path).path

        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self.send_json_response(400, {"error": "Invalid Content-Length header."})
            return

        if content_length <= 0:
            self.send_json_response(400, {"error": "Empty request body."})
            return

        if content_length > MAX_POST_BODY_BYTES:
            # Drain up to a small chunk if needed and return 413 Payload Too Large
            self.send_json_response(
                413,
                {"error": "Request body exceeds the 5 MB maximum limit."}
            )
            return

        try:
            body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(body)
        except Exception as e:
            self.send_json_response(400, {"error": f"Invalid JSON body: {str(e)}"})
            return

        if route_path == "/api/analyze":
            resume_text = payload.get("resume_text", "")
            job_desc = payload.get("job_description", "")
            if not resume_text or not job_desc:
                self.send_json_response(400, {"error": "Both 'resume_text' and 'job_description' are required."})
                return

            try:
                result = analyze_ats_match(resume_text, job_desc)
                # Check for optional filename or format hint
                format_hint = payload.get("format") or payload.get("filename") or payload.get("file_type")
                if format_hint:
                    result["format_findings"] = audit_text_format(resume_text)
                self.send_json_response(200, result)
            except Exception as e:
                self.send_json_response(500, {"error": f"Analysis failed: {str(e)}"})

        elif route_path == "/api/enhance-bullet":
            bullet = payload.get("bullet", "")
            if not bullet:
                self.send_json_response(400, {"error": "Field 'bullet' is required."})
                return
            result = analyze_bullet_point(bullet)
            self.send_json_response(200, result)

        else:
            self.send_json_response(404, {"error": "API route not found."})


def run_server(host: str = "127.0.0.1", port: int = 8080):
    httpd = None
    for p in range(port, port + 10):
        try:
            server_address = (host, p)
            httpd = ThreadingHTTPServer(server_address, OpenATSRequestHandler)
            port = p
            break
        except OSError:
            continue

    if httpd is None:
        raise OSError(f"Could not bind OpenATS server to {host} on ports {port}-{port+9}")

    print(f"\n" + "=" * 62)
    print(f" ⚡ OpenATS v{__version__} — High-Performance ATS Resume Engine")
    print(f" 👤 Created by: {__author__}")
    print(f" 🌐 GitHub: {__repository__}")
    print(f" 🚀 Local Dashboard: http://{host}:{port}")
    print(f"=" * 62 + "\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping OpenATS server gracefully...")
        httpd.server_close()
