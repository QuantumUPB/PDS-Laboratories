"""Small HTTP app for Lab 4. Complete build_event and send_event."""

import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen


OPENSEARCH_URL = os.environ.get("OPENSEARCH_URL", "http://opensearch:9200")


def build_event(path: str, status: int) -> dict:
    """TODO: Return a log event with @timestamp, service, path, status, and message."""
    # Use datetime.now(timezone.utc).isoformat() for the timestamp.
    # Give successful and missing paths different messages.
    raise NotImplementedError("Complete build_event in app/app.py")


def send_event(event: dict) -> None:
    """TODO: POST one JSON event to /lab-logs/_doc?refresh=wait_for."""
    # Encode with json.dumps(event).encode("utf-8").
    # Build a Request with method="POST" and Content-Type: application/json.
    # Open it with urlopen(..., timeout=5) so the request is actually sent.
    raise NotImplementedError("Complete send_event in app/app.py")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        status = 200 if self.path == "/items" else 404
        try:
            send_event(build_event(self.path, status))
        except Exception as error:
            self.send_error(503, f"Log delivery failed: {error}")
            return

        body = json.dumps({"items": ["disk", "bucket"]} if status == 200 else {"error": "not found"}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print("Lab app listening on port 8080", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
