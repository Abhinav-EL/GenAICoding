import os
import unittest
import time
import random
import string
from urllib.parse import quote

from MyImpl.simpleFlaskApp import create_test_app

"""
***** FIRST Prompt: For a simple Flask App with the following "/api/greet/" GET api call, what input could break this?
@app.route('/api/greet/', methods=['GET']) def greet(name): return jsonify(message=f"Hello, {name}!")

Respose: 
Short answer: lots of inputs can cause unexpected behavior. The endpoint is very permissive (it just interpolates the path component into a JSON string), so you should consider and guard against:

Path-routing issues
Names containing slashes: "John/Smith" — by default a plain "" route will treat a slash as a path separator, so you either get only "John" or no match. Using "path:name [blocked]" or sending the value as a query parameter avoids that.
Percent-encoding edge cases: "/api/greet/John%2FSmith" and other percent-encoded sequences may route unexpectedly or be decoded differently by clients/servers.
Extremely long input (DoS)
Very large names (e.g. 'a' * 10_000_000) can exhaust memory/CPU or be abused for denial-of-service.
Binary / encoding problems
Non-UTF-8 or malformed byte sequences could cause decoding errors if the client/transport mis-declares encoding.
Embedded NUL ( %00 ), CRLF (%0D%0A) or other control characters: may not break jsonify itself (it will escape control chars), but can create odd behavior when the string is used elsewhere.
XSS/HTML injection (client-side risk)
Name containing HTML/JS: "" — the JSON response is safe as JSON, but if a client naïvely injects message straight into an HTML page without escaping, that becomes a cross-site scripting risk.
Unexpected characters
Emoji and other Unicode characters — usually fine, but test client handling and DB/storage later.
Quotes, backslashes, JSON control chars — jsonify will JSON-escape these correctly, but if downstream code assumes unescaped content, that can cause problems.
Special payloads that may be interpreted by downstream code
If you later use name in shell commands, SQL, HTML templates, or file paths, inputs like "'; DROP TABLE users; --" or "../../etc/passwd" create injection/path-traversal risks (not a problem for this isolated endpoint, but dangerous in real apps).
HTTP method / header issues
Non-GET requests -> 405. Very long header values or headers containing strange values could create other problems (not specific to this route).


***** SECOND Prompt: How can we improve the security and robustness of the "/api/greet/" endpoint?
"""

class TestGreetSRE(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_test_app()
        cls.client = cls.app.test_client()
        # Whether to run heavier SRE-like tests (set env RUN_SRE_HEAVY_TESTS=1)
        cls.run_heavy = os.getenv("RUN_SRE_HEAVY_TESTS", "") == "1"

    def _get(self, path, raw=False):
        """Helper to GET a path. If raw is False, path components will be safe-quoted by caller."""
        return self.client.get(path)

    def _get_with_name(self, name, quote_name=True):
        """Construct path for /api/greet/<name>. If quote_name True, percent-encode the name."""
        if quote_name:
            enc = quote(name, safe='')
            path = f'/api/greet/{enc}'
        else:
            path = f'/api/greet/{name}'
        return self.client.get(path)

    def _assert_no_5xx(self, resp):
        """SRE: ensure server did not return an internal error for unexpected inputs."""
        self.assertNotEqual(resp.status_code // 100, 5, msg=f"Server error for path; status={resp.status_code}; body={resp.data!r}")

    def test_basic_name(self):
        resp = self._get_with_name("Alice")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content_type.split(';')[0], 'application/json')
        body = resp.get_json()
        self.assertIn("message", body)
        self.assertEqual(body["message"], "Hello, Alice!")

    def test_empty_name_route_not_found(self):
        # /api/greet/ with no name should not match the route -> 404
        resp = self._get('/api/greet/')
        self.assertEqual(resp.status_code, 404)

    def test_name_with_slash_is_404(self):
        # A literal slash in the path creates extra path segment; route uses single segment -> expect 404
        resp = self._get_with_name("John/Smith", quote_name=False)
        # depending on routing this should be a 404 (route mismatch)
        self.assertEqual(resp.status_code, 404)

    def test_percent_encoded_slash_behavior(self):
        # Behavior may vary between frameworks/servers; ensure we don't get a 5xx.
        resp = self._get_with_name("John/Smith", quote_name=True)  # will send %2F
        self._assert_no_5xx(resp)
        # If we got 200, check message contains something sensible (either decoded or percent form)
        if resp.status_code == 200:
            body = resp.get_json()
            self.assertIn("message", body)
            msg = body["message"]
            self.assertTrue("John" in msg and "Smith" in msg)
            # either contains literal slash or percent-encoded form
            self.assertTrue("/" in msg or "%2F" in msg)

    def test_long_name(self):
        # Simulate a long but not extreme name; heavy tests disabled by default
        long_name = "a" * 100_000  # 100k characters
        resp = self._get_with_name(long_name)
        # Ensure server responds (not 500) and returns JSON
        self._assert_no_5xx(resp)
        if resp.status_code == 200:
            body = resp.get_json()
            self.assertIn("message", body)
            self.assertTrue(body["message"].startswith("Hello, "))
            # ensure a portion of the long payload is reflected back
            self.assertTrue(body["message"][7:20] == long_name[:13])

    def test_control_characters(self):
        # Names with newline and null bytes should not crash the server.
        for name in ["Bob\nSmith", "Eve\r\nSmith", "Null\x00Char"]:
            resp = self._get_with_name(name, quote_name=True)
            self._assert_no_5xx(resp)
            if resp.status_code == 200:
                body = resp.get_json()
                # JSON decoding should succeed
                self.assertIn("message", body)
                # The returned message should include the sequence (it may be escaped in JSON)
                self.assertTrue("Hello," in body["message"])

    def test_unicode_and_emoji(self):
        name = "José 👩‍💻"
        resp = self._get_with_name(name)
        self._assert_no_5xx(resp)
        if resp.status_code == 200:
            body = resp.get_json()
            self.assertEqual(body["message"], f"Hello, {name}")

    def test_json_escaping_and_injection_chars(self):
        # Ensure characters like quotes, backslashes and script tags don't break JSON response
        name = '"\\/<script>alert(1)</script>'
        resp = self._get_with_name(name)
        self._assert_no_5xx(resp)
        if resp.status_code == 200:
            # JSON should parse successfully
            body = resp.get_json()
            self.assertIn("message", body)
            # The returned message should include the same characters (client-side must escape when rendering in HTML)
            self.assertTrue('script' in body["message"])

    def test_sequential_light_load(self):
        # A lightweight sequential load: many small requests; default 100 requests.
        # This is a simple SRE smoke test to look for timeouts or 5xxs.
        n = 100
        start = time.time()
        for i in range(n):
            resp = self._get_with_name(f"user{i}")
            self._assert_no_5xx(resp)
            self.assertEqual(resp.status_code, 200)
        elapsed = time.time() - start
        avg_ms = (elapsed / n) * 1000
        # We allow a generous threshold; change as appropriate for your environment.
        self.assertLess(avg_ms, 200, msg=f"Average request time too high: {avg_ms:.1f}ms")

    def test_fuzz_small_inputs_no_5xx(self):
        # Random small fuzz inputs; ensure the app doesn't return 5xx for weird inputs.
        for _ in range(50):
            # random printable + some control bytes
            raw = ''.join(random.choice(string.printable + '\x00\x01\x02') for _ in range(random.randint(1, 40)))
            resp = self._get_with_name(raw, quote_name=True)
            # SRE-level assertion: no 5xx errors
            self._assert_no_5xx(resp)
            # Accept 200 or 404; main goal is no internal server error
            self.assertIn(resp.status_code, (200, 404))

    @unittest.skipUnless(os.getenv("RUN_SRE_HEAVY_TESTS") == "1", "heavy SRE tests disabled (set RUN_SRE_HEAVY_TESTS=1)")
    def test_spike_load_simulation(self):
        # Heavier test: burst of concurrent-ish requests simulated sequentially.
        # This is intentionally lightweight and sequential here; real load tests should use k6/locust.
        n = 1000
        start = time.time()
        errors = 0
        for i in range(n):
            resp = self._get_with_name("spike")
            if resp.status_code // 100 == 5:
                errors += 1
        elapsed = time.time() - start
        # Ensure not many 5xxs
        self.assertEqual(errors, 0, msg=f"{errors} server errors during spike")
        self.assertLess(elapsed, 30, msg="Spike test took too long; investigate performance")

if __name__ == '__main__':
    unittest.main()
