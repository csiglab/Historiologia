#!/usr/bin/env python3
"""Thin static + read-only API server for Historiologia.

Serves app/ as the web root (stdlib only, no dependencies, no database):

    /                         -> app/index.html (hub)
    /about.html               -> app/about.html
    /note/                    -> 301 /note/web/ (relative ../data/ fetches keep working)
    /note/web/<file>          -> app/note/web/<file> (catalog + reader)
    /note/data/<file>         -> app/note/data/<file> (.md/.html/.json corpus)
    /shared/<file>            -> app/shared/<file> (theme, vendor, img)

Read-only API (same origin, for curl/embedding; the pages fetch static
JSON directly and work from any static host without this server):

    GET /api/health           -> {service, notes, sections, words, generated}
    GET /api/search?q=        -> ranked matches over search-index.json
    GET /api/index            -> the full notes index (alias)

Usage:
    python app.py [--port 8000] [--root app]

Environment (.env):
    PORT=8022  HOST=0.0.0.0  (explicit flags win over the environment)
"""

import argparse
import json
import mimetypes
import os
import re
import urllib.parse
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

NOTE_SEGMENT_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
BLOCKED = ("agents.md", "guideline.md")


def valid_note_path(name: str) -> bool:
    if len(name) > 200 or "\x00" in name:
        return False
    parts = [p for p in name.split("/") if p not in ("", ".")]
    if not parts or ".." in parts:
        return False
    *dirs, filename = parts
    if not filename.endswith((".md", ".html")):
        return False
    stem = filename.rsplit(".", 1)[0]
    if not NOTE_SEGMENT_RE.match(stem):
        return False
    return all(NOTE_SEGMENT_RE.match(d) for d in dirs)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def score(entry: dict, q: str) -> int:
    title = str(entry.get("title", "")).lower()
    tags = [str(t).lower() for t in entry.get("tags", [])]
    path = str(entry.get("path", "")).lower()
    excerpt = str(entry.get("excerpt", "")).lower()
    if title.startswith(q):
        return 0
    if q in title:
        return 1
    if any(q in t for t in tags) or q in path:
        return 2
    if q in excerpt:
        return 3
    return 9


class Handler(SimpleHTTPRequestHandler):
    root: Path = Path("app")
    server_version = "Historiologia/1.0"

    def log_message(self, *args):  # quieter default logging
        pass

    def _send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, path: Path):
        if not path.is_file():
            self.send_error(404)
            return
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix in (".html", ".css", ".js", ".json", ".md"):
            ctype += "; charset=utf-8" if "charset" not in ctype else ""
        try:
            body = path.read_bytes()
        except OSError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlsplit(self.path)
        route, qs = parsed.path, urllib.parse.parse_qs(parsed.query)
        low = route.lower()

        if any(seg in BLOCKED for seg in low.split("/")) or "/." in low:
            self.send_error(404)
            return

        if route in ("/api/health", "/api/health/"):
            metrics = load_json(self.root / "data" / "landing-metrics.json") or {}
            self._send_json(
                {
                    "service": "historiologia",
                    "notes": metrics.get("notes"),
                    "sections": metrics.get("sections", {}),
                    "words": metrics.get("words"),
                    "generated": metrics.get("generated"),
                }
            )
            return

        if route in ("/api/index", "/api/index/"):
            idx = load_json(self.root / "note" / "data" / "index.json")
            if idx is None:
                self.send_error(503, "notes index not built (run: make notes-index)")
                return
            self._send_json(idx)
            return

        if route in ("/api/search", "/api/search/"):
            q = (qs.get("q", [""])[0] or "").strip().lower()
            sidx = load_json(self.root / "data" / "search-index.json")
            if sidx is None:
                self.send_error(503, "search index not built (run: make search-index)")
                return
            entries = sidx.get("entries", [])
            if not q:
                self._send_json({"q": "", "results": []})
                return
            ranked = sorted(
                ((score(e, q), e) for e in entries if score(e, q) < 9),
                key=lambda t: (t[0], str(t[1].get("title", ""))),
            )
            self._send_json({"q": q, "results": [e for _, e in ranked[:24]]})
            return

        if route == "/note/api/pins":
            # No database in Historiologia: pins are unsupported; the catalog
            # hides pin UI when this endpoint is unreachable.
            self.send_error(503, "pins unsupported (static-only, no database)")
            return

        if route == "/" or route == "":
            return self._serve_file(self.root / "index.html")
        if route == "/note" or route == "/note/":
            self.send_response(301)
            self.send_header("Location", "/note/web/")
            self.end_headers()
            return
        if route == "/note/web" or route == "/note/web/":
            return self._serve_file(self.root / "note" / "web" / "index.html")

        # Static files under the app root (note.html?n= validated client-side;
        # data paths validated here for a clean 404 on bad slugs).
        if route.startswith("/note/data/"):
            rel = route[len("/note/data/") :]
            if rel.endswith((".md", ".html")) and not valid_note_path(rel):
                self.send_error(404)
                return
            return self._serve_file(self.root / "note" / "data" / rel.lstrip("/"))

        rel = route.lstrip("/")
        if rel and (self.root / rel).is_file():
            return self._serve_file(self.root / rel)

        return self.send_error(404)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    ap.add_argument("--root", default="app")
    ap.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    args = ap.parse_args()
    Handler.root = Path(args.root).resolve()
    httpd = HTTPServer((args.host, args.port), Handler)
    print(f"historiologia: serving {Handler.root} on http://{args.host}:{args.port}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
