from __future__ import annotations

import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable


def run_oauth_callback(
    auth_url: str,
    expected_path: str = "/callback",
    port: int = 8400,
) -> dict[str, str]:
    """브라우저 OAuth 후 redirect query params 반환."""
    result: dict[str, str] = {}
    done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != expected_path:
                self.send_response(404)
                self.end_headers()
                return
            result.update(dict(urllib.parse.parse_qsl(parsed.query)))
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("인증 완료. 이 창을 닫고 터미널로 돌아가세요.".encode())
            done.set()

        def log_message(self, *_args: object) -> None:
            return

    redirect_uri = f"http://localhost:{port}{expected_path}"
    url = auth_url if "redirect_uri=" in auth_url else f"{auth_url}&redirect_uri={urllib.parse.quote(redirect_uri)}"
    server = HTTPServer(("localhost", port), Handler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    webbrowser.open(url)
    done.wait(timeout=300)
    server.server_close()
    if not result:
        raise TimeoutError("OAuth 콜백 타임아웃 (5분)")
    if "error" in result:
        raise RuntimeError(result.get("error_description") or result["error"])
    return result
