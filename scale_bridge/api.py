import json
from dataclasses import fields
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .state import ScaleStateEngine, ScaleStateError, WeighingContext

LOOPBACK_HOST = "127.0.0.1"


def create_server(engine: ScaleStateEngine, *, port=8765, allowed_origins=()):
    origins = frozenset(allowed_origins)
    if not origins or "*" in origins:
        raise ValueError("an explicit non-wildcard Origin allowlist is required")
    handler = _handler_for(engine, origins)
    return ThreadingHTTPServer((LOOPBACK_HOST, port), handler)


def _handler_for(engine, allowed_origins):
    class Handler(BaseHTTPRequestHandler):
        server_version = "IDS701ScaleBridge/0.1"

        def do_OPTIONS(self):
            if not self._origin_allowed(optional=False, respond=False):
                return self._json(403, {"error": "ORIGIN_NOT_ALLOWED"})
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", self.headers["Origin"])
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Vary", "Origin")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            if not self._origin_allowed(optional=True):
                return
            path = urlsplit(self.path).path
            if path == "/health":
                self._json(200, {"status": "ok"})
            elif path in {"/status", "/reading"}:
                self._json(200, engine.snapshot())
            else:
                self._json(404, {"error": "NOT_FOUND"})

        def do_POST(self):
            if not self._origin_allowed(optional=False):
                return
            path = urlsplit(self.path).path
            try:
                if path == "/tare/capture":
                    engine.capture_tare()
                elif path == "/tare/clear":
                    engine.clear_tare()
                elif path == "/context":
                    payload = self._json_body()
                    allowed = {field.name for field in fields(WeighingContext)}
                    if set(payload) - allowed:
                        return self._json(400, {"error": "INVALID_CONTEXT_FIELD"})
                    engine.set_context(WeighingContext(**payload))
                else:
                    return self._json(404, {"error": "NOT_FOUND"})
            except (ScaleStateError, TypeError, ValueError) as exc:
                reason = getattr(exc, "reason", "INVALID_REQUEST")
                return self._json(409, {"error": reason, "state": engine.snapshot()})
            self._json(200, engine.snapshot())

        def _origin_allowed(self, *, optional, respond=True):
            origin = self.headers.get("Origin")
            if origin is None and optional:
                return True
            if origin not in allowed_origins:
                if respond:
                    self._json(403, {"error": "ORIGIN_NOT_ALLOWED"})
                return False
            return True

        def _json_body(self):
            length = int(self.headers.get("Content-Length", "0"))
            if length > 4096:
                raise ValueError("request too large")
            return json.loads(self.rfile.read(length) or b"{}")

        def _json(self, status, payload):
            body = json.dumps(payload, separators=(",", ":")).encode()
            self.send_response(status)
            origin = self.headers.get("Origin")
            if origin in allowed_origins:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            return

    return Handler
