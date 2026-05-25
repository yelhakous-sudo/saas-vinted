import http.server
import urllib.request
import urllib.error
import os
import sys
import json
import io

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
BACKEND_URL = "http://localhost:8001"
PORT = 3000

MIME_MAP = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".webp": "image/webp",
}

class FrontendHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=FRONTEND_DIR, **kwargs)

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self._proxy_api()
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            return self._proxy_api()
        self.send_error(405)

    def _proxy_api(self):
        target = f"{BACKEND_URL}{self.path}"
        try:
            body = None
            if self.command == "POST":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length) if length > 0 else None

            req = urllib.request.Request(
                target,
                data=body,
                headers={k: v for k, v in self.headers.items() if k.lower() not in ("host", "connection")},
                method=self.command,
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                self.send_response(resp.status)
                ct = resp.headers.get("Content-Type", "application/json")
                self.send_header("Content-Type", ct)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            data = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_error(502, f"Proxy error: {str(e)}")

    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path) or not os.path.exists(path):
            index = os.path.join(path if os.path.isdir(path) else FRONTEND_DIR, "index.html")
            if os.path.exists(index):
                self.path = "/index.html"
                return super().send_head()
        return super().send_head()

    def guess_type(self, path):
        ext = os.path.splitext(path)[1].lower()
        return MIME_MAP.get(ext) or super().guess_type(path)

if __name__ == "__main__":
    print(f"Serving frontend on http://localhost:{PORT}")
    print(f"Proxying /api/* to {BACKEND_URL}")
    httpd = http.server.HTTPServer(("0.0.0.0", PORT), FrontendHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        httpd.shutdown()
