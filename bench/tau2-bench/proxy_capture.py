#!/usr/bin/env python3
"""Transparent logging proxy for the determinism probe.

Forwards POSTs verbatim between tau2 (api_base pointed here) and the engine,
and appends one JSONL line per /v1/chat/completions call: the exact request
body plus the engine's assistant message + usage. The instrument is unmodified;
only the network path is instrumented (disclosed in the wave RECORD).

Usage: proxy_capture.py <out.jsonl> [port]
"""
import json, sys, threading, time, urllib.error, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

OUT = sys.argv[1]
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8011
ENGINE = "http://127.0.0.1:8000"
lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n)
        req = urllib.request.Request(ENGINE + self.path, data=raw, method="POST",
                                     headers={"Content-Type": "application/json"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                body = r.read()
                code = r.status
        except urllib.error.HTTPError as e:
            body = e.read()
            code = e.code
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        if self.path.endswith("/chat/completions") and code == 200:
            try:
                reqj = json.loads(raw)
                resp = json.loads(body)
                ch = (resp.get("choices") or [{}])[0]
                rec = {"t": t0, "ms": round((time.time() - t0) * 1000),
                       "request": reqj, "message": ch.get("message"),
                       "finish_reason": ch.get("finish_reason"), "usage": resp.get("usage")}
                with lock, open(OUT, "a") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            except Exception:
                pass  # never break the served path for the probe's sake

    def do_GET(self):
        req = urllib.request.Request(ENGINE + self.path, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                body, code = r.read(), r.status
        except urllib.error.HTTPError as e:
            body, code = e.read(), e.code
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
