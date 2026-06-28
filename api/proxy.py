"""Vercel serverless proxy to bypass CORS on the PCC API."""

import json
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

PCC_BASE = "https://hackathon.prod.pulsefoundry.ai"


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        endpoint = qs.get("endpoint", [None])[0]
        if not endpoint:
            self._respond(400, {"error": "Missing 'endpoint' query param"})
            return

        params = {k: v[0] for k, v in qs.items() if k != "endpoint"}
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{PCC_BASE}{endpoint}"
        if query_string:
            url += f"?{query_string}"

        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
                status = resp.status
                self._respond(status, json.loads(body), raw=True)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8") if e.fp else "{}"
            retry_after = e.headers.get("Retry-After", "")
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            if retry_after:
                self.send_header("Retry-After", retry_after)
            self.end_headers()
            self.wfile.write(body.encode())
        except Exception as e:
            self._respond(502, {"error": str(e)})

    def _respond(self, status, data, raw=False):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if raw and isinstance(data, (list, dict)):
            self.wfile.write(json.dumps(data).encode())
        else:
            self.wfile.write(json.dumps(data).encode())
