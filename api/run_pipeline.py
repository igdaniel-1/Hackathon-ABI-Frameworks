"""Vercel serverless function: triggers the pipeline and returns results."""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.runner import PipelineRunner


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        openai_key = os.environ.get("OPENAI_API_KEY")
        if not openai_key:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "OPENAI_API_KEY not configured"}).encode())
            return

        try:
            runner = PipelineRunner(openai_api_key=openai_key)
            results = runner.run()
            output = [r.to_dict() for r in results]

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(output, indent=2).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
