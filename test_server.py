import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
import server  # noqa: E402  (reads DATA_DIR at import)

GOOD = {
    "interval": 20,
    "layouts": [{"id": "wall", "name": "Wall", "hosts": ["nuc", "dozor"]}],
    "rotation": [{"host": "nuc"}, {"layout": "wall"}, {"layout": "all"}],
}


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server.DATA_DIR.mkdir(parents=True, exist_ok=True)
        server.CONFIG_PATH.write_text(Path(server.DEFAULT_CONFIG).read_text())
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def req(self, method, path, body=None, ctype="application/json", headers=None):
        data = body if isinstance(body, bytes) else (json.dumps(body).encode() if body is not None else None)
        r = urllib.request.Request(self.base + path, data=data, method=method, headers=headers or {})
        if data is not None:
            r.add_header("Content-Type", ctype)
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, resp.read(), resp.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers

    def test_put_saves_and_never_takes_hosts_from_client(self):
        status, body, _ = self.req("PUT", "/api/config", {**GOOD, "hosts": [{"id": "evil", "name": "x", "url": "http://x"}]})
        self.assertEqual(status, 200)
        saved = json.loads(self.req("GET", "/api/config")[1])
        self.assertEqual(saved["interval"], 20)
        self.assertEqual(saved["layouts"], GOOD["layouts"])
        self.assertEqual([h["id"] for h in saved["hosts"]], ["almaz", "nuc", "dozor", "buran", "kvant"])

    def test_etag_gives_304(self):
        etag = self.req("GET", "/api/config")[2]["ETag"]
        status, _, _ = self.req("GET", "/api/config", headers={"If-None-Match": etag})
        self.assertEqual(status, 304)

    def test_rejects_bad_input(self):
        bad = [
            {**GOOD, "interval": 1},
            {**GOOD, "interval": "30"},
            {**GOOD, "rotation": []},
            {**GOOD, "rotation": [{"host": "nope"}]},
            {**GOOD, "rotation": [{"layout": "missing"}]},
            {**GOOD, "layouts": [{"id": "all", "name": "x", "hosts": ["nuc"]}]},
            {**GOOD, "layouts": [{"id": "a", "name": "x", "hosts": []}]},
            {**GOOD, "layouts": [{"id": "a", "name": "x", "hosts": ["nope"]}]},
        ]
        for b in bad:
            self.assertEqual(self.req("PUT", "/api/config", b)[0], 400, b)

    def test_requires_json_content_type(self):
        self.assertEqual(self.req("PUT", "/api/config", b"{}", ctype="text/plain")[0], 415)

    def test_page_and_health(self):
        self.assertEqual(self.req("GET", "/healthz")[0], 200)
        status, body, _ = self.req("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Glances viewer", body)


if __name__ == "__main__":
    unittest.main()
