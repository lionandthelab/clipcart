"""b-roll 소싱: Pexels 실영상/사진 우선, Gemini 생성 이미지 폴백.

steward-lab role_models/shorts/pexels.py + gemini_image.py 를 clipcart로 포팅.
키는 .env(TYPECAST/PEXELS/GEMINI). 모든 함수는 soft-fail(None 반환).
"""

from __future__ import annotations

import hashlib
import io
import os
import urllib.parse
import urllib.request

from clipcart.config import PROJECT_ROOT

CACHE = PROJECT_ROOT / "tools" / ".cache"
PEXELS_CACHE = CACHE / "pexels"
GEMINI_CACHE = CACHE / "gemini"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) clipcart/1.0"
_API_VIDEO = "https://api.pexels.com/videos/search"
_API_PHOTO = "https://api.pexels.com/v1/search"


def _key(name: str) -> str:
    return (os.getenv(name, "") or "").split("#")[0].strip()


# --------------------------------------------------------------------------- #
# Pexels
# --------------------------------------------------------------------------- #
class Pexels:
    def __init__(self) -> None:
        self.key = _key("PEXELS_API_KEY")
        PEXELS_CACHE.mkdir(parents=True, exist_ok=True)

    @property
    def enabled(self) -> bool:
        return bool(self.key)

    def _get(self, url: str) -> dict | None:
        if not self.key:
            return None
        req = urllib.request.Request(url, headers={"Authorization": self.key, "User-Agent": _UA})
        try:
            import json

            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            print(f"  [pexels] query failed: {str(e)[:120]}")
            return None

    def _download(self, url: str, suffix: str, tag: str) -> str | None:
        h = hashlib.md5(f"{tag}|{url}".encode()).hexdigest()[:16]
        dest = PEXELS_CACHE / f"{h}{suffix}"
        if dest.exists() and dest.stat().st_size > 1024:
            return str(dest)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            dest.write_bytes(data)
            return str(dest)
        except Exception as e:  # noqa: BLE001
            print(f"  [pexels] download failed: {str(e)[:120]}")
            return None

    @staticmethod
    def _best_video_file(video: dict, want_h: int = 1920) -> str | None:
        files = video.get("video_files", [])
        portrait = [f for f in files if (f.get("height") or 0) >= (f.get("width") or 1)]
        pool = portrait or files
        if not pool:
            return None
        good = [f for f in pool if (f.get("height") or 0) >= 1280]
        chosen = min(good or pool, key=lambda f: abs((f.get("height") or 0) - want_h))
        return chosen.get("link")

    def fetch_video(self, query: str, index: int = 0, min_duration: int = 3) -> str | None:
        if not self.key:
            return None
        q = urllib.parse.quote(query)
        data = self._get(f"{_API_VIDEO}?query={q}&orientation=portrait&size=medium&per_page=15")
        if not data:
            return None
        vids = [v for v in data.get("videos", []) if (v.get("duration") or 0) >= min_duration]
        vids = vids or data.get("videos", [])
        if not vids:
            return None
        v = vids[index % len(vids)]
        link = self._best_video_file(v)
        return self._download(link, ".mp4", f"vid|{query}|{index}") if link else None

    def fetch_photo(self, query: str, index: int = 0) -> str | None:
        if not self.key:
            return None
        q = urllib.parse.quote(query)
        data = self._get(f"{_API_PHOTO}?query={q}&orientation=portrait&per_page=15")
        if not data:
            return None
        photos = data.get("photos", [])
        if not photos:
            return None
        p = photos[index % len(photos)]
        src = p.get("src", {})
        link = src.get("portrait") or src.get("large2x") or src.get("large")
        return self._download(link, ".jpg", f"pho|{query}|{index}") if link else None


# --------------------------------------------------------------------------- #
# Gemini still (candid / cinematic / simple)
# --------------------------------------------------------------------------- #
_GEMINI_CINEMATIC = (
    "Cinematic dramatic film still, real Korean home interior, atmospheric natural "
    "lighting, shallow depth of field, photoreal, vertical 9:16, no text. Subject: "
)
_GEMINI_SIMPLE = (
    "Clean realistic lifestyle photo, Korean household, bright, vertical 9:16, no text. Subject: "
)
# AI티 제거용: 사람/손 없이 배경·상황만, 일상 폰카 스냅풍 (문제 장면 공감용)
_GEMINI_CANDID = (
    "Candid amateur smartphone snapshot, ordinary lived-in Korean apartment, natural "
    "unstaged daylight, slightly imperfect casual framing, realistic textures and "
    "clutter, photorealistic, vertical 9:16. Absolutely no people, no hands, no faces, "
    "no text, no watermark. Scene: "
)
_GEMINI_STYLES = {"cinematic": _GEMINI_CINEMATIC, "simple": _GEMINI_SIMPLE, "candid": _GEMINI_CANDID}


def _gemini_client():
    try:
        from google import genai

        key = _key("GEMINI_API_KEY")
        return genai.Client(api_key=key) if key else None
    except Exception:
        return None


def gemini_still(subject: str, style: str = "cinematic", index: int = 0) -> str | None:
    client = _gemini_client()
    if client is None:
        return None
    GEMINI_CACHE.mkdir(parents=True, exist_ok=True)
    h = hashlib.md5(f"{style}|{subject}|{index}".encode()).hexdigest()[:14]
    dest = GEMINI_CACHE / f"gen_{style}_{h}.png"
    if dest.exists() and dest.stat().st_size > 1024:
        return str(dest)
    prefix = _GEMINI_STYLES.get(style, _GEMINI_SIMPLE)
    try:
        from google.genai import types
        from PIL import Image

        resp = client.models.generate_content(
            model="gemini-3.1-flash-image-preview",
            contents=prefix + subject,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio="9:16", image_size="512"),
            ),
        )
        data = None
        for part in (resp.parts or []):
            if getattr(part, "inline_data", None) is not None:
                data = part.inline_data.data
                break
        if not data and resp.candidates:
            for part in (resp.candidates[0].content.parts or []):
                if getattr(part, "inline_data", None) is not None:
                    data = part.inline_data.data
                    break
        if not data:
            return None
        Image.open(io.BytesIO(data)).convert("RGB").save(dest, "PNG")
        return str(dest)
    except Exception as e:  # noqa: BLE001
        print(f"  [gemini] still failed: {str(e)[:120]}")
        return None


# 제품 화보샷: 쇼핑몰 제품컷(누끼/흰배경)을 입력으로 주고, 제품은 그대로 둔 채
# 예쁜 배경·구도로 '촬영한 듯한' 이미지를 만든다. 제품 변형 방지 지시 포함.
_PRODUCT_SHOT_PROMPT = (
    "Take the exact product from the input photo and place it in this setting: {scene}. "
    "Looks like a real product photo taken with a good camera: soft natural window "
    "light, shallow depth of field, pleasing composition, minimal tasteful props. "
    "Keep the product COMPLETELY IDENTICAL to the input — same shape, same colors, "
    "same logos and printing, do not redesign or beautify the product itself. "
    "Vertical 9:16. No people, no hands, no text, no watermark."
)


def gemini_product_shot(product_image_path: str, scene: str, index: int = 0) -> str | None:
    """제품 이미지 → 스타일 배경 화보샷 (image-to-image). 실패 시 None(soft-fail)."""
    client = _gemini_client()
    if client is None:
        return None
    GEMINI_CACHE.mkdir(parents=True, exist_ok=True)
    try:
        src_bytes = open(product_image_path, "rb").read()
    except OSError:
        return None
    h = hashlib.md5(b"pshot|" + src_bytes[:4096] + f"|{scene}|{index}".encode()).hexdigest()[:14]
    dest = GEMINI_CACHE / f"pshot_{h}.png"
    if dest.exists() and dest.stat().st_size > 1024:
        return str(dest)
    try:
        from google.genai import types
        from PIL import Image

        resp = client.models.generate_content(
            model="gemini-3.1-flash-image-preview",
            contents=[
                types.Part.from_bytes(data=src_bytes, mime_type="image/png"),
                _PRODUCT_SHOT_PROMPT.format(scene=scene),
            ],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio="9:16", image_size="1K"),
            ),
        )
        data = None
        for part in (resp.parts or []):
            if getattr(part, "inline_data", None) is not None:
                data = part.inline_data.data
                break
        if not data and resp.candidates:
            for part in (resp.candidates[0].content.parts or []):
                if getattr(part, "inline_data", None) is not None:
                    data = part.inline_data.data
                    break
        if not data:
            return None
        Image.open(io.BytesIO(data)).convert("RGB").save(dest, "PNG")
        return str(dest)
    except Exception as e:  # noqa: BLE001
        print(f"  [gemini] product shot failed: {str(e)[:120]}")
        return None
