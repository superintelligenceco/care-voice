"""A tiny local HTTP server used by tests instead of any real network service."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

Responder = Callable[[str, dict[str, str], bytes], tuple[int, Any]]


@contextmanager
def local_server(respond: Responder) -> Iterator[tuple[str, list[dict[str, Any]]]]:
    """Run an HTTP server on 127.0.0.1 and yield ``(base_url, requests)``."""
    requests: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:
            pass

        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            headers = dict(self.headers.items())
            requests.append({"path": self.path, "headers": headers, "body": body})
            status, payload = respond(self.path, headers, body)
            data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, args=(0.05,), daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", requests
    finally:
        server.shutdown()
        server.server_close()
