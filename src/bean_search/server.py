"""Tiny stdlib web server for the bean map UI.

GET  /                -> the game page
GET  /static/<file>   -> static assets
GET  /api/goals       -> every bean on the graph
GET  /api/search?lat=&lon=&moves=[&width=&branch=]  -> beam search result
"""

import json
import logging
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import networkx as nx

from .search import BeanSearcher, result_to_json

STATIC_DIR = Path(__file__).parent / "web"
MAX_MOVES = 2000
log = logging.getLogger(__name__)


def make_handler(G: nx.MultiDiGraph, searcher: BeanSearcher):
    lock = threading.Lock()  # searcher's cache is not thread-safe
    goals_payload = {
        "region": G.graph.get("region"),
        "mean_edge_m": searcher.mean_edge_m,
        "goals": [
            {
                "id": str(g),
                "name": G.nodes[g].get("name"),
                "bean_type": G.nodes[g]["bean_type"],
                "lat": G.nodes[g]["y"],
                "lon": G.nodes[g]["x"],
            }
            for g in searcher.goals
        ],
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            log.info("%s - %s", self.address_string(), fmt % args)

        def _send(self, status: int, body: bytes, ctype: str):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, status=200):
            self._send(status, json.dumps(obj).encode(), "application/json")

        def do_GET(self):
            url = urlparse(self.path)
            if url.path in ("/", "/index.html"):
                return self._static("index.html")
            if url.path.startswith("/static/"):
                return self._static(url.path.removeprefix("/static/"))
            if url.path == "/api/goals":
                return self._json(goals_payload)
            if url.path == "/api/search":
                return self._search(parse_qs(url.query))
            self._json({"error": "not found"}, 404)

        def _static(self, name: str):
            path = (STATIC_DIR / name).resolve()
            if STATIC_DIR.resolve() not in path.parents or not path.is_file():
                return self._json({"error": "not found"}, 404)
            ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            self._send(200, path.read_bytes(), ctype)

        def _search(self, q: dict):
            try:
                lat = float(q["lat"][0])
                lon = float(q["lon"][0])
                moves = int(q.get("moves", ["150"])[0])
                width = int(q.get("width", ["8"])[0])
                branch = int(q.get("branch", ["4"])[0])
            except (KeyError, ValueError):
                return self._json({"error": "need numeric lat, lon, moves"}, 400)
            if not (1 <= moves <= MAX_MOVES and 1 <= width <= 64 and 1 <= branch <= 16):
                return self._json({"error": f"moves must be 1..{MAX_MOVES}"}, 400)
            with lock:
                start = searcher.nearest_road_node(lat, lon)
                res = searcher.search(start, moves, width=width, branch=branch)
                self._json(result_to_json(G, res))

    return Handler


def serve(G: nx.MultiDiGraph, host: str = "127.0.0.1", port: int = 8000) -> None:
    searcher = BeanSearcher(G)
    httpd = ThreadingHTTPServer((host, port), make_handler(G, searcher))
    print(f"Bean map running at http://{host}:{port}  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
