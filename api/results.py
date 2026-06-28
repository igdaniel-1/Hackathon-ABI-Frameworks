"""Vercel serverless function: serves cached pipeline results."""

import json
import os
from http.server import BaseHTTPRequestHandler

RESULTS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "results.json")


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if os.path.exists(RESULTS_PATH):
            with open(RESULTS_PATH, "r") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data.encode())
        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "No results found. Run the pipeline first via GET /api/run_pipeline"
            }).encode())
