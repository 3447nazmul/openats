"""
Integration Tests for OpenATS HTTP Server & APIs (Agent 5: QC Test Suite).
Verifies endpoints, query-string routing, 5 MB POST size limits, strict CORS,
security headers, and 1-hour update checker caching.
"""
import os
import sys
import unittest
import threading
import time
import urllib.request
import urllib.error
import json
from http.server import ThreadingHTTPServer
from unittest.mock import patch, MagicMock

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openats.server import OpenATSRequestHandler, MAX_POST_BODY_BYTES
from openats.updater import check_for_updates, clear_update_cache


class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = 8899
        cls.server = ThreadingHTTPServer(("127.0.0.1", cls.port), OpenATSRequestHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        for _ in range(50):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{cls.port}/api/health", timeout=1) as resp:
                    if resp.status == 200:
                        break
            except Exception:
                time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_health_endpoint(self):
        req = urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/health")
        self.assertEqual(req.status, 200)
        self.assertEqual(req.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(req.headers.get("Referrer-Policy"), "no-referrer")
        data = json.loads(req.read().decode())
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["app"], "OpenATS")

    def test_query_string_url_serves_page(self):
        """Verify query-string URLs (/index.html?x=1 and /?ref=test) return 200 HTML and security headers."""
        for path in ("/index.html?x=1", "/?utm_source=github&test=1"):
            res = urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}")
            self.assertEqual(res.status, 200)
            self.assertIn("text/html", res.headers.get("Content-Type", ""))
            self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
            self.assertEqual(res.headers.get("Referrer-Policy"), "no-referrer")
            self.assertIsNotNone(res.headers.get("Content-Security-Policy"))
            body = res.read().decode("utf-8")
            self.assertIn("OpenATS", body)

    def test_oversized_post_returns_413(self):
        """Verify POST requests exceeding 5 MB return HTTP 413 with a JSON error."""
        # Create a request declaring Content-Length > 5 MB
        small_body = b'{"resume_text": "a", "job_description": "b"}'
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/analyze",
            data=small_body,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(MAX_POST_BODY_BYTES + 1024),
            },
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 413)
        err_data = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertIn("5 MB", err_data.get("error", ""))

    def test_cors_header_not_wildcard_for_cross_origin(self):
        """Verify CORS reflects matching localhost origin and NEVER returns '*' for cross-origin requests."""
        # 1. Cross-origin request from evil.example.com
        req_cross = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/health",
            headers={"Origin": "https://evil.example.com"},
        )
        res_cross = urllib.request.urlopen(req_cross)
        self.assertEqual(res_cross.status, 200)
        acao_cross = res_cross.headers.get("Access-Control-Allow-Origin")
        self.assertIsNone(acao_cross)
        self.assertNotEqual(acao_cross, "*")

        # 2. Same-port localhost Origin is reflected
        allowed_origin = f"http://localhost:{self.port}"
        req_local = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/health",
            headers={"Origin": allowed_origin},
        )
        res_local = urllib.request.urlopen(req_local)
        self.assertEqual(res_local.headers.get("Access-Control-Allow-Origin"), allowed_origin)

    def test_check_update_in_process_caching(self):
        """Verify /api/check-update caches the GitHub API response in-process for 1 hour."""
        clear_update_cache()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "tag_name": "v1.0.0",
            "html_url": "https://github.com/3447nazmul/openats/releases/tag/v1.0.0",
            "body": "Release notes"
        }).encode("utf-8")
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
            r1 = check_for_updates("1.0.0", use_cache=True)
            r2 = check_for_updates("1.0.0", use_cache=True)
            self.assertEqual(r1["current_version"], "1.0.0")
            self.assertEqual(r2["current_version"], "1.0.0")
            # urlopen should have been called ONLY ONCE due to 1-hour cache
            self.assertEqual(mock_urlopen.call_count, 1)

    def test_analyze_api(self):
        payload = json.dumps({
            "resume_text": "Software engineer with Python and Docker. Email: me@test.com Phone: 555-1234. Experience: • Deployed system reducing load by 15%.",
            "job_description": "Looking for Software Engineer with Python, Docker, and AWS."
        }).encode("utf-8")

        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/analyze",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        res = urllib.request.urlopen(req)
        self.assertEqual(res.status, 200)
        data = json.loads(res.read().decode())
        self.assertIn("final_score", data)
        self.assertIn("sub_scores", data)
        self.assertIn("matched_keywords", data)

    def test_enhance_bullet_api(self):
        payload = json.dumps({"bullet": "Worked on server optimization."}).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/enhance-bullet",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        res = urllib.request.urlopen(req)
        self.assertEqual(res.status, 200)
        data = json.loads(res.read().decode())
        self.assertIn("suggested_rewrites", data)
        self.assertIn("score", data)


if __name__ == "__main__":
    unittest.main()
