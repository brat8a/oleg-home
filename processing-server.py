#!/usr/bin/env python3
"""Local text-processing server for a running Ollama instance."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.error import URLError
from urllib.request import Request, urlopen

PAGE = """<!doctype html><html lang="ru"><meta charset="utf-8">
<title>Свой ИИ в рут Алисы</title><h1>Свой ИИ в рут Алисы</h1>
<form><label>Сообщение <textarea maxlength="4000" required></textarea></label>
<button>Отправить</button></form><pre aria-live="polite"></pre>
<script>
const form = document.querySelector('form'), output = document.querySelector('pre');
const button = form.querySelector('button');
form.onsubmit = async (event) => {
  event.preventDefault();
  button.disabled = true;
  output.textContent = 'Обработка…';
  try {
    const response = await fetch('/chat', {method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({text: form.querySelector('textarea').value})});
    const result = await response.json();
    output.textContent = result.reply || result.error;
  } catch {
    output.textContent = 'Сервер недоступен';
  } finally {
    button.disabled = false;
  }
};
</script></html>"""

class Handler(BaseHTTPRequestHandler):
    def send_body(self, status, content, media_type="application/json"):
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", media_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self.send_body(200, PAGE, "text/html")
        elif self.path == "/health":
            self.send_body(200, '{"status":"ok"}')
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/chat":
            self.send_error(404)
            return
        try:
            origin = self.headers.get("Origin")
            expected = f"http://127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") != expected.removeprefix("http://") or origin not in (None, expected):
                self.send_error(403)
                return
            if self.headers.get_content_type() != "application/json":
                raise ValueError
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 32768:
                raise ValueError
            self.connection.settimeout(10)
            payload = json.loads(self.rfile.read(size))
            message = payload.get("text") if isinstance(payload, dict) else None
            if not isinstance(message, str) or not 0 < len(message.strip()) <= 4000:
                raise ValueError
        except (ValueError, TimeoutError):
            self.send_body(400, '{"error":"Expected JSON with a text field (1–4000 characters)."}')
            return
        request = Request(
            "http://127.0.0.1:11434/api/chat",
            data=json.dumps({"model": self.server.model, "stream": False,
                             "messages": [{"role": "user", "content": message}]}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=120) as response:
                reply = json.load(response)["message"]["content"]
        except (URLError, TimeoutError, ValueError, KeyError, TypeError):
            self.send_body(502, '{"error":"Ollama unavailable or model not installed."}')
            return
        self.send_body(200, json.dumps({"reply": reply}, ensure_ascii=False))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="Name shown by ollama list")
    parser.add_argument("--port", type=int, default=8787)
    options = parser.parse_args()
    with HTTPServer(("127.0.0.1", options.port), Handler) as server:
        server.model = options.model
        print(f"Open http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    main()
