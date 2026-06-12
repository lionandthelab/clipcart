"""OpenRouter 경유 Kling I2V — 제품 화보샷을 첫 프레임 레퍼런스로 5초 모션 클립 생성.

pave(app/infrastructure/external_apis/openrouter_client.py)의 패턴을 clipcart에
맞게 경량 포팅했다: POST /api/v1/videos 제출 → GET /videos/{id} 폴링 →
(인증 필요 시 Bearer로) 다운로드. 모든 함수는 soft-fail(None) — 실패하면
호출측이 정지 화보샷으로 폴백한다.

비용 주의: 클립당 과금되므로 (이미지+프롬프트) 해시로 캐시해 재렌더 시
재과금을 막는다. 끄려면 CLIPCART_KLING=off.
"""

from __future__ import annotations

import base64
import hashlib
import os
import time
from typing import Any

import requests

from clipcart.config import PROJECT_ROOT

API_BASE = "https://openrouter.ai/api/v1"
CACHE = PROJECT_ROOT / "tools" / ".cache" / "kling"

_MODEL_DEFAULT = "kwaivgi/kling-v3.0-pro"


def _model() -> str:
    return os.getenv("CLIPCART_KLING_MODEL", _MODEL_DEFAULT)


def _key() -> str:
    return (os.getenv("OPENROUTER_API_KEY", "") or "").split("#")[0].strip()


def enabled() -> bool:
    if os.getenv("CLIPCART_KLING", "on").lower() in ("off", "0", "false"):
        return False
    return bool(_key())


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_key()}", "Content-Type": "application/json"}


def _payload(image_data_uri: str, prompt: str, duration: int = 5) -> dict[str, Any]:
    return {
        "model": _model(),
        "prompt": prompt or "",
        "duration": int(duration),
        "aspect_ratio": "9:16",
        "resolution": os.getenv("CLIPCART_KLING_RESOLUTION", "720p"),
        "frame_images": [
            {
                "type": "image_url",
                "image_url": {"url": image_data_uri},
                "frame_type": "first_frame",
            }
        ],
        # 내레이션(TTS)과 충돌하지 않도록 네이티브 오디오는 항상 끈다
        "generate_audio": False,
    }


def _accepted(status_code: int) -> bool:
    """제출 성공 판정 — OpenRouter는 비동기 작업을 202(Accepted)로 받는다."""
    return status_code in (200, 201, 202)


def _parse_status(data: dict[str, Any]) -> tuple[str, str | None]:
    """OpenRouter 응답 → ('success'|'processing'|'failed', video_url)."""
    status = (data.get("status") or "").lower()
    if status == "completed":
        url = None
        unsigned = data.get("unsigned_urls") or data.get("urls") or []
        if isinstance(unsigned, list) and unsigned:
            first = unsigned[0]
            url = first if isinstance(first, str) else (first or {}).get("url")
        url = url or data.get("video_url") or data.get("output_url")
        return ("success", url) if url else ("failed", None)
    if status in ("failed", "error", "cancelled"):
        return "failed", None
    return "processing", None


def animate(
    image_path: str,
    prompt: str,
    duration: int = 5,
    timeout_s: int = 420,
    poll_s: int = 10,
) -> str | None:
    """이미지 → Kling 모션 클립 mp4 경로. 실패/비활성 시 None(soft-fail)."""
    if not enabled():
        return None
    try:
        raw = open(image_path, "rb").read()
    except OSError:
        return None

    h = hashlib.md5(
        b"kling|" + raw[:8192] + f"|{prompt}|{duration}|{_model()}".encode()
    ).hexdigest()[:16]
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / f"k_{h}.mp4"
    if dest.exists() and dest.stat().st_size > 50_000:
        return str(dest)

    try:
        uri = "data:image/png;base64," + base64.b64encode(raw).decode()
        resp = requests.post(
            f"{API_BASE}/videos",
            headers=_headers(),
            json=_payload(uri, prompt, duration),
            timeout=120,
        )
        if not _accepted(resp.status_code):
            print(f"  [kling] 작업 생성 실패 {resp.status_code}: {resp.text[:150]}")
            return None
        body = resp.json()
        task_id = body.get("id") or body.get("task_id")
        if not task_id:
            print(f"  [kling] task_id 없음: {str(body)[:150]}")
            return None

        t0 = time.time()
        while time.time() - t0 < timeout_s:
            time.sleep(poll_s)
            s = requests.get(f"{API_BASE}/videos/{task_id}", headers=_headers(), timeout=30)
            if s.status_code != 200:
                continue
            state, url = _parse_status(s.json())
            if state == "failed":
                print("  [kling] 생성 실패 (모더레이션/업스트림)")
                return None
            if state == "success" and url:
                dl_headers = _headers() if url.startswith(API_BASE) else {}
                with requests.get(url, headers=dl_headers, stream=True, timeout=180) as r:
                    r.raise_for_status()
                    with open(dest, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                if dest.exists() and dest.stat().st_size > 50_000:
                    return str(dest)
                return None
        print(f"  [kling] 타임아웃({timeout_s}s)")
        return None
    except Exception as e:  # noqa: BLE001
        print(f"  [kling] 실패: {str(e)[:150]}")
        return None
