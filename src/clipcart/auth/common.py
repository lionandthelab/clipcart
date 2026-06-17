from __future__ import annotations

import os
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


def resolve_redirect_uri(port: int = 8400, path: str = "/callback") -> str:
    """OAuth redirect URI 결정. 자체 공개 콜백(CLIPCART_OAUTH_REDIRECT, 예:
    https://acts.run/callback/)이 있으면 그걸 쓰고, 없으면 localhost loopback.
    Meta/Pinterest/TikTok 이 같은 값을 공유해 한 콜백 페이지로 통일한다."""
    override = (os.getenv("CLIPCART_OAUTH_REDIRECT", "") or "").strip()
    return override or f"http://localhost:{port}{path}"


def is_loopback(uri: str) -> bool:
    return uri.startswith("http://localhost") or uri.startswith("http://127.0.0.1")


def parse_pasted(pasted: str) -> dict[str, str]:
    """붙여넣은 값(전체 리다이렉트 URL 또는 code 단독)에서 code/state 추출."""
    pasted = pasted.strip()
    if "code=" in pasted or "?" in pasted:
        query = urllib.parse.urlparse(pasted).query or pasted.split("?", 1)[-1]
        parsed = dict(urllib.parse.parse_qsl(query))
        if parsed.get("code"):
            return parsed
    return {"code": pasted}  # code 단독 붙여넣기


def manual_paste_flow(auth_url: str, redirect_uri: str, label: str = "OAuth") -> dict[str, str]:
    """공개 HTTPS 콜백 페이지로 인증 → 거기 표시된 code 를 붙여넣는 수동 플로우."""
    print(f"\n[{label} 인증]")
    print("1) 아래 URL 을 브라우저에서 열고 승인하세요(자동으로도 열림):\n")
    print(auth_url + "\n")
    print(f"2) 승인 후 '{redirect_uri}' 페이지에 표시된 code(또는 전체 URL)를 복사하세요.\n")
    try:
        webbrowser.open(auth_url)
    except Exception:  # noqa: BLE001
        pass
    pasted = input("3) code 또는 전체 리다이렉트 URL 붙여넣기: ").strip()
    if not pasted:
        raise RuntimeError("입력이 비어 있음")
    return parse_pasted(pasted)


def collect_oauth(
    auth_url: str, redirect_uri: str, port: int = 8400, label: str = "OAuth"
) -> dict[str, str]:
    """redirect_uri 가 loopback 이면 로컬 서버 자동 캐치, 공개 URL 이면 수동 붙여넣기."""
    if is_loopback(redirect_uri):
        return run_oauth_callback(auth_url, port=port)
    return manual_paste_flow(auth_url, redirect_uri, label=label)
