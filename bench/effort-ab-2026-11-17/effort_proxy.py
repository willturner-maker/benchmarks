#!/usr/bin/env python3
"""Logging + effort-injecting proxy in front of Splash, for the effort A/B.

Listens on 8010, forwards to 8000. Records every /v1/chat/completions body header line
(model, effort present?, injected effort, messages count, max_tokens) and the response usage
(reasoning tokens) to a JSONL next to the proxy. If EFFORT env is set, it is INJECTED into the
body as reasoning_effort — that is the arm mechanism if the harness cannot forward effort itself.

Every request stays fully visible to the engine as coming from 127.0.0.1; the proxy is a
transparent pipe, and its log is the audit of what each arm actually sent.
"""
import json, os, pathlib, threading, time, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TARGET = "http://127.0.0.1:8000"
EFFORT = os.environ.get("PROXY_EFFORT")          # e.g. "medium"; unset = pass through untouched
LOG = pathlib.Path(os.environ.get("PROXY_LOG", "proxy-audit.jsonl"))
PORT = int(os.environ.get("PROXY_PORT", "8010"))
_lock = threading.Lock()

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _proxy(self):
        body = b""
        n = int(self.headers.get("Content-Length") or 0)
        if n: body = self.rfile.read(n)
        note = {"ts": time.strftime("%H:%M:%S"), "ms": int(time.time() * 1000), "port": PORT,
                "path": self.path, "method": self.command}
        send = body
        if self.path.startswith("/v1/chat/completions") and body:
            try:
                d = json.loads(body)
                note.update({"model": d.get("model"),
                             "effort_in_body": d.get("reasoning_effort"),
                             "effort_injected": None,
                             "max_tokens": d.get("max_tokens"),
                             "msgs": len(d.get("messages") or [])})
                if EFFORT:
                    d["reasoning_effort"] = EFFORT
                    note["effort_injected"] = EFFORT
                    send = json.dumps(d).encode()
            except Exception as e:
                note["body_parse_error"] = str(e)[:80]
        req = urllib.request.Request(TARGET + self.path, data=send if self.command == "POST" else None,
                                     headers={k: v for k, v in self.headers.items()
                                              if k.lower() not in ("host", "content-length")},
                                     method=self.command)
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                data = r.read()
                note.update({"status": r.status, "len": len(data)})
                if self.path.startswith("/v1/chat/completions"):
                    try:
                        u = (json.loads(data).get("usage") or {})
                        note["completion_tokens"] = u.get("completion_tokens")
                        note["reasoning_tokens"] = (u.get("completion_tokens_details") or {}).get("reasoning_tokens")
                    except Exception: pass
                self.send_response(r.status)
                for k, v in r.headers.items():
                    if k.lower() not in ("transfer-encoding", "connection", "content-length"):
                        self.send_header(k, v)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            data = e.read()
            self.send_response(e.code)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            note.update({"status": e.code, "err": data[:120].decode(errors="ignore")})
        except Exception as e:
            note["error"] = str(e)[:120]
            self.send_error(502, str(e)[:80])
        with _lock:
            with open(LOG, "a") as f: f.write(json.dumps(note) + "\n")

    do_GET = do_POST = do_OPTIONS = _proxy

if __name__ == "__main__":
    print(f"proxy :{PORT} -> {TARGET} | effort={'passthrough' if not EFFORT else EFFORT} | log={LOG}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
