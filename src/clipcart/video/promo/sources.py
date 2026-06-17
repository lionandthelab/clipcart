"""b-roll 소싱: Pexels 실영상/사진 우선, Gemini 생성 이미지 폴백.

steward-lab role_models/shorts/pexels.py + gemini_image.py 를 clipcart로 포팅.
키는 .env(TYPECAST/PEXELS/GEMINI). 모든 함수는 soft-fail(None 반환).
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import urllib.parse
import urllib.request

from clipcart.config import PROJECT_ROOT
from clipcart.video.promo.template import is_story

CACHE = PROJECT_ROOT / "tools" / ".cache"
PEXELS_CACHE = CACHE / "pexels"
GEMINI_CACHE = CACHE / "gemini"
OPENROUTER_CACHE = CACHE / "openrouter"
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
# 모던 단서를 명시: 그냥 'Korean home'이면 20년 전 낡은 인테리어가 나온다.
# 2020년대 신축 아파트(현대식 마감/가전)로 고정해 시청자 공감도를 높인다.
_MODERN_KR = (
    "a modern 2020s South Korean apartment, contemporary newly-built interior with "
    "recent fixtures and appliances (not old or dated)"
)
_GEMINI_CINEMATIC = (
    f"Cinematic dramatic film still inside {_MODERN_KR}, atmospheric natural "
    "lighting, shallow depth of field, photoreal, vertical 9:16, no text. Subject: "
)
_GEMINI_SIMPLE = (
    f"Clean realistic lifestyle photo inside {_MODERN_KR}, bright, vertical 9:16, no text. Subject: "
)
# AI티 제거용: 사람/손 없이 배경·상황만, 일상 폰카 스냅풍 (문제 장면 공감용)
_GEMINI_CANDID = (
    f"Candid amateur smartphone snapshot inside {_MODERN_KR}, natural "
    "unstaged daylight, slightly imperfect casual framing, realistic textures and "
    "clutter, photorealistic, vertical 9:16. Absolutely no people, no hands, no faces, "
    "no text, no watermark. Scene: "
)
# story 템플릿용 — 밝고 화사한 모던 릴스 미감(하이키·파스텔·소프트 블룸). 사람/손 없음.
_GEMINI_STORY = (
    f"Soft bright airy lifestyle photo inside {_MODERN_KR}. High-key soft diffused "
    "natural window light, gently overexposed background, low contrast, pastel cream and "
    "off-white palette, subtle bloom and halation glow on highlights, soft shadows, "
    "shallow depth of field, film-like pastel color grade, clean minimal modern styling, "
    "lots of negative space, warm cozy slow-morning mood. Absolutely no people, no hands, "
    "no faces, no text, no watermark. Vertical 9:16. Scene: "
)
_GEMINI_STYLES = {
    "cinematic": _GEMINI_CINEMATIC,
    "simple": _GEMINI_SIMPLE,
    "candid": _GEMINI_CANDID,
    "story": _GEMINI_STORY,
}


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
# story 템플릿용 — 밝고 화사한 라이프스타일 화보(제품은 그대로).
_PRODUCT_SHOT_PROMPT_STORY = (
    "Take the exact product from the input photo and place it in this setting: {scene}. "
    "Looks like a soft bright lifestyle product photo: high-key diffused natural window "
    "light, airy pastel cream background, gentle bloom, low contrast, shallow depth of "
    "field, minimal tasteful cream-toned props, lots of negative space. "
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
    story = is_story()
    tkey = "story" if story else "promo"
    h = hashlib.md5(
        b"pshot|" + src_bytes[:4096] + f"|{scene}|{index}|{tkey}".encode()
    ).hexdigest()[:14]
    dest = GEMINI_CACHE / f"pshot_{h}.png"
    if dest.exists() and dest.stat().st_size > 1024:
        return str(dest)
    prompt = _PRODUCT_SHOT_PROMPT_STORY if story else _PRODUCT_SHOT_PROMPT
    try:
        from google.genai import types
        from PIL import Image

        resp = client.models.generate_content(
            model="gemini-3.1-flash-image-preview",
            contents=[
                types.Part.from_bytes(data=src_bytes, mime_type="image/png"),
                prompt.format(scene=scene),
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


# --------------------------------------------------------------------------- #
# OpenRouter 이미지 모델 (실사 품질 업그레이드) — env CLIPCART_IMAGE_MODEL로 켠다.
# 예: openai/gpt-5.4-image-2 (실사·지시따름 최상), google/gemini-3-pro-image-preview.
# 미설정이면 기존 Gemini를 그대로 쓴다(동작·비용 불변).
# --------------------------------------------------------------------------- #
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def image_model() -> str:
    return (os.getenv("CLIPCART_IMAGE_MODEL", "") or "").split("#")[0].strip()


def image_size() -> str:
    """비용 절감용 출력 해상도. 가장 낮게 — GPT-image-2는 0.5K 미지원(HTTP 400)이라
    1K가 최저. 9:16과 함께 720x1280(최소 면적, 세로 영상과 일치)."""
    return (os.getenv("CLIPCART_IMAGE_SIZE", "") or "1K").split("#")[0].strip()


def _openrouter_image(content, cache_tag: str) -> str | None:
    """OpenRouter 이미지 모델 호출(modalities=image,text) → png 경로. soft-fail(None)."""
    key = _key("OPENROUTER_API_KEY")
    model = image_model()
    if not key or not model:
        return None
    OPENROUTER_CACHE.mkdir(parents=True, exist_ok=True)
    h = hashlib.md5(f"{model}|{image_size()}|{cache_tag}".encode()).hexdigest()[:16]
    dest = OPENROUTER_CACHE / f"or_{h}.png"
    if dest.exists() and dest.stat().st_size > 1024:
        return str(dest)
    body = json.dumps(
        {"model": model, "messages": [{"role": "user", "content": content}],
         "modalities": ["image", "text"],
         # 비용 절감: 최저 해상도 + 세로(9:16). 면적이 가장 작아 토큰/비용 최소.
         "image_config": {"image_size": image_size(), "aspect_ratio": "9:16"}}
    ).encode()
    req = urllib.request.Request(
        OPENROUTER_URL, data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": _UA},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.load(r)
        imgs = (data.get("choices") or [{}])[0].get("message", {}).get("images") or []
        if not imgs:
            return None
        url = imgs[0].get("image_url", {}).get("url", "")
        if not url.startswith("data:"):
            return None
        raw = base64.b64decode(url.split(",", 1)[1])
        from PIL import Image

        Image.open(io.BytesIO(raw)).convert("RGB").save(dest, "PNG")
        return str(dest) if dest.stat().st_size > 1024 else None
    except Exception as e:  # noqa: BLE001
        print(f"  [openrouter] image failed ({model}): {str(e)[:120]}")
        return None


def openrouter_still(subject: str, style: str = "story", index: int = 0) -> str | None:
    prefix = _GEMINI_STYLES.get(style, _GEMINI_SIMPLE)
    return _openrouter_image(prefix + subject, f"still|{style}|{subject}|{index}")


def openrouter_product_shot(product_image_path: str, scene: str, index: int = 0) -> str | None:
    try:
        src_bytes = open(product_image_path, "rb").read()
    except OSError:
        return None
    prompt = (_PRODUCT_SHOT_PROMPT_STORY if is_story() else _PRODUCT_SHOT_PROMPT).format(scene=scene)
    b64 = base64.b64encode(src_bytes).decode()
    content = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
    ]
    tag = hashlib.md5(
        b"pshot|" + src_bytes[:4096] + f"|{scene}|{index}|{'story' if is_story() else 'promo'}".encode()
    ).hexdigest()[:14]
    return _openrouter_image(content, f"pshot|{tag}")


def openrouter_compose(prompt: str, image_paths: list[str], cache_tag: str) -> str | None:
    """여러 레퍼런스 이미지(제품 + 직전 컷 등)를 함께 주고 합성. 인물·제품 일관성용.

    image_paths 순서대로 레퍼런스로 전달된다(보통 [제품, 이전컷]). soft-fail(None).
    """
    content: list = [{"type": "text", "text": prompt}]
    ref_sig = b""
    for p in image_paths:
        try:
            raw = open(p, "rb").read()
        except OSError:
            continue
        ref_sig += raw[:2048]
        b64 = base64.b64encode(raw).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
    if len(content) == 1:  # 레퍼런스 이미지가 하나도 없으면 의미 없음
        return None
    tag = hashlib.md5(b"compose|" + ref_sig + f"|{cache_tag}".encode()).hexdigest()[:16]
    return _openrouter_image(content, f"compose|{tag}")


def generate_still(subject: str, style: str = "candid", index: int = 0) -> str | None:
    """텍스트→이미지. OpenRouter 모델이 켜져 있으면 우선(실사 품질), 실패 시 Gemini."""
    if image_model():
        p = openrouter_still(subject, style, index)
        if p:
            return p
    return gemini_still(subject, style, index)


def generate_product_shot(product_image_path: str, scene: str, index: int = 0) -> str | None:
    """제품 화보샷(image-to-image). OpenRouter 우선(실사), 실패 시 Gemini."""
    if image_model():
        p = openrouter_product_shot(product_image_path, scene, index)
        if p:
            return p
    return gemini_product_shot(product_image_path, scene, index)
