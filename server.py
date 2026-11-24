#!/usr/bin/env python3
"""Serve the Glances viewer page and save its settings.

GET  /api/config   current settings (ETag)
PUT  /api/config   replace layouts, rotation and interval (hosts are never taken from the client)
GET  /healthz      "ok"

Environment: PORT (8080), DATA_DIR (/data), PUBLIC_DIR (./public), DEFAULT_CONFIG (./config.default.json)
"""
import hashlib
import json
import os
import re
import shutil
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
PUBLIC_DIR = Path(os.environ.get("PUBLIC_DIR", HERE / "public"))
DEFAULT_CONFIG = Path(os.environ.get("DEFAULT_CONFIG", HERE / "config.default.json"))
CONFIG_PATH = DATA_DIR / "config.json"
MAX_BODY = 64 * 1024
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
RESERVED_LAYOUT_IDS = {"all"}


class Invalid(ValueError):
    pass


def load_config():
    return json.loads(CONFIG_PATH.read_text())


def save_config(cfg):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=DATA_DIR, prefix=".config-")
    with os.fdopen(fd, "w") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")
    os.replace(tmp, CONFIG_PATH)


def validate_update(body, hosts):
    """Return the new layouts, rotation and interval, or raise Invalid."""
    if not isinstance(body, dict):
        raise Invalid("body must be an object")
    host_ids = {h["id"] for h in hosts}

    interval = body.get("interval")
    if isinstance(interval, bool) or not isinstance(interval, int) or not 5 <= interval <= 3600:
        raise Invalid("interval must be a whole number of seconds, 5 to 3600")

    layouts = body.get("layouts")
    if not isinstance(layouts, list) or len(layouts) > 50:
        raise Invalid("layouts must be a list of at most 50")
    seen = set()
    clean_layouts = []
    for lay in layouts:
        if not isinstance(lay, dict):
            raise Invalid("each layout must be an object")
        lid, name, members = lay.get("id"), lay.get("name"), lay.get("hosts")
        if not isinstance(lid, str) or not ID_RE.match(lid) or lid in RESERVED_LAYOUT_IDS:
            raise Invalid(f"bad layout id: {lid!r}")
        if lid in seen:
            raise Invalid(f"duplicate layout id: {lid}")
        seen.add(lid)
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 60:
            raise Invalid("layout name must be 1 to 60 characters")
        if not isinstance(members, list) or not members or any(m not in host_ids for m in members):
            raise Invalid(f"layout {lid} needs at least one known host")
        clean_layouts.append({"id": lid, "name": name.strip(), "hosts": list(dict.fromkeys(members))})

    rotation = body.get("rotation")
    if not isinstance(rotation, list) or not 1 <= len(rotation) <= 100:
        raise Invalid("rotation must have 1 to 100 items")
    clean_rotation = []
    for item in rotation:
        if not isinstance(item, dict) or len(item) != 1:
            raise Invalid("each rotation item is {host: id} or {layout: id}")
        ((kind, ref),) = item.items()
        if kind == "host" and ref in host_ids:
            clean_rotation.append({"host": ref})
        elif kind == "layout" and (ref in seen or ref in RESERVED_LAYOUT_IDS):
            clean_rotation.append({"layout": ref})
        else:
            raise Invalid(f"unknown rotation item: {item}")

    return clean_layouts, clean_rotation, interval


class Handler(BaseHTTPRequestHandler):
    server_version = "glances-viewer"

    def log_message(self, fmt, *args):
        print(self.address_string(), fmt % args, flush=True)

    def send_bytes(self, status, data, content_type, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, status, obj, extra=None):
        self.send_bytes(status, json.dumps(obj).encode(), "application/json", extra)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/healthz":
            return self.send_bytes(200, b"ok", "text/plain")
        if path == "/api/config":
            data = CONFIG_PATH.read_bytes()
            etag = '"' + hashlib.sha256(data).hexdigest()[:16] + '"'
            if self.headers.get("If-None-Match") == etag:
                self.send_response(304)
                self.send_header("ETag", etag)
                self.end_headers()
                return
            return self.send_bytes(200, data, "application/json", {"ETag": etag})
        if path in ("/", "/index.html"):
            return self.send_bytes(200, (PUBLIC_DIR / "index.html").read_bytes(), "text/html; charset=utf-8")
        self.send_bytes(404, b"not found", "text/plain")

    def do_PUT(self):
        if self.path.split("?", 1)[0] != "/api/config":
            return self.send_bytes(404, b"not found", "text/plain")
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            return self.send_json(415, {"error": "send application/json"})
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self.send_json(411, {"error": "Content-Length required"})
        if length > MAX_BODY:
            return self.send_json(413, {"error": "body too large"})
        try:
            body = json.loads(self.rfile.read(length))
            cfg = load_config()
            cfg["layouts"], cfg["rotation"], cfg["interval"] = validate_update(body, cfg["hosts"])
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self.send_json(400, {"error": "invalid JSON"})
        except Invalid as e:
            return self.send_json(400, {"error": str(e)})
        save_config(cfg)
        self.send_json(200, cfg)


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        shutil.copy(DEFAULT_CONFIG, CONFIG_PATH)
    port = int(os.environ.get("PORT", "8080"))
    print(f"listening on :{port}, config {CONFIG_PATH}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
