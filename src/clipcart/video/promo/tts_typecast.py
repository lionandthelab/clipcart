"""Typecast 한국어 내레이션 (프로모션 톤) + edge-tts 폴백.

steward-lab missionary_series/tts_typecast.py 패턴 포팅. 비트 tone → 감정 프리셋.
ffmpeg로 라우드니스 정규화 + atempo로 급박한 템포(기본 1.12x).
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from functools import lru_cache
from pathlib import Path

from clipcart.config import PROJECT_ROOT
from clipcart.video.ff import ffmpeg_exe, media_duration

TTS_CACHE = PROJECT_ROOT / "tools" / ".cache" / "tts_kr"

# 진희 — 또렷한 아나운서 여성 (프로모션/광고 표준 톤). env로 교체 가능.
DEFAULT_VOICE_ID = "tc_6731b2b2478a48710ecc9158"
TEMPO = float(os.getenv("CLIPCART_TTS_TEMPO", "1.24"))

# 비트 tone → (감정 프리셋, 강도)
_TONE_EMOTION = {
    "hook": ("happy", 1.3),
    "problem": ("sad", 1.1),
    "switch": ("sad", 1.2),  # 기존 방식 실망 공감 → 직후 product(happy)로 전환 아크
    "product": ("happy", 1.2),
    "usage": ("happy", 1.0),
    "result": ("happy", 1.3),
    "cta": ("happy", 1.2),
    "neutral": ("normal", 1.0),
}


def _key() -> str:
    return (os.getenv("TYPECAST_API_KEY", "") or "").split("#")[0].strip()


def _voice_id() -> str:
    return (os.getenv("CLIPCART_TTS_VOICE_ID", "") or "").strip() or DEFAULT_VOICE_ID


@lru_cache(maxsize=1)
def _client_and_voice():
    """(client, voice_meta) 또는 (None, None)."""
    key = _key()
    if not key:
        return None, None
    try:
        from typecast import Typecast

        client = Typecast(api_key=key)
        vid = _voice_id()
        meta = {"voice_id": vid, "model": "ssfm-v30", "emotions": []}
        try:
            for v in client.voices():
                if v.voice_id == vid:
                    meta = {"voice_id": vid, "model": v.model, "emotions": list(v.emotions)}
                    break
        except Exception:  # noqa: BLE001
            pass
        return client, meta
    except Exception as e:  # noqa: BLE001
        print(f"  [typecast] init failed: {str(e)[:120]}")
        return None, None


def available() -> bool:
    client, _ = _client_and_voice()
    return client is not None


def _normalize(path: Path) -> None:
    """라우드니스 정규화 + atempo(급박한 템포)."""
    try:
        tmp = path.with_suffix(".norm.mp3")
        af = f"atempo={TEMPO:.3f},loudnorm=I=-16:TP=-1.5:LRA=11"
        subprocess.run(
            [ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(path),
             "-filter:a", af, "-ar", "44100", "-b:a", "160k", str(tmp)],
            capture_output=True, timeout=60,
        )
        if tmp.exists() and tmp.stat().st_size > 1000:
            tmp.replace(path)
    except Exception as e:  # noqa: BLE001
        print(f"  [typecast] normalize failed: {str(e)[:80]}")


def _cache_path(text: str, tone: str) -> Path:
    h = hashlib.md5(f"{text}|{_voice_id()}|{tone}|{TEMPO}".encode("utf-8")).hexdigest()[:16]
    return TTS_CACHE / f"tc_{h}.mp3"


def synth(text: str, tone: str, out: Path | None = None) -> tuple[Path, float] | None:
    """Typecast 합성 → (path, duration). 실패 시 None."""
    TTS_CACHE.mkdir(parents=True, exist_ok=True)
    cache = _cache_path(text, tone)
    if cache.exists() and cache.stat().st_size > 1000:
        try:
            return cache, media_duration(cache)
        except Exception:  # noqa: BLE001
            cache.unlink(missing_ok=True)

    client, meta = _client_and_voice()
    if client is None:
        return None
    emotion, intensity = _TONE_EMOTION.get(tone, _TONE_EMOTION["neutral"])
    if emotion not in (meta.get("emotions") or []) and emotion != "normal":
        emotion = "happy" if "happy" in (meta.get("emotions") or []) else "normal"
    try:
        from typecast.models import Output, Prompt, TTSRequest

        resp = client.text_to_speech(
            TTSRequest(
                text=text,
                voice_id=meta["voice_id"],
                model=meta["model"],
                language="kor",
                prompt=Prompt(emotion_preset=emotion, emotion_intensity=intensity),
                output=Output(audio_format="mp3", volume=100),
            )
        )
        cache.write_bytes(resp.audio_data)
        _normalize(cache)
        dur = media_duration(cache)
        if dur <= 0:
            cache.unlink(missing_ok=True)
            return None
        return cache, dur
    except Exception as e:  # noqa: BLE001
        print(f"  [typecast] synth failed: {str(e)[:120]}")
        return None


def synth_or_edge(text: str, tone: str) -> tuple[Path, float]:
    """Typecast 우선, 실패 시 edge-tts 폴백. (path, duration) 보장."""
    res = synth(text, tone)
    if res is not None:
        return res
    # edge-tts 폴백
    from clipcart.video.tts import synthesize

    h = hashlib.md5(f"edge|{text}|{tone}".encode("utf-8")).hexdigest()[:16]
    path = TTS_CACHE / f"edge_{h}.mp3"
    synthesize(text, path, rate="+18%")
    return path, media_duration(path)
