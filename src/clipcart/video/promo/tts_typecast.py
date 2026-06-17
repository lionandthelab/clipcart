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
from clipcart.video.promo.template import is_story

TTS_CACHE = PROJECT_ROOT / "tools" / ".cache" / "tts_kr"

# 진희 — 또렷한 아나운서 여성 (프로모션/광고 표준 톤). env로 교체 가능.
DEFAULT_VOICE_ID = "tc_6731b2b2478a48710ecc9158"


def _tempo() -> float:
    """말 속도. env 우선 → story는 자연스럽게 빠른 1.13(운영자 선택), promo는 1.24."""
    env = (os.getenv("CLIPCART_TTS_TEMPO", "") or "").strip()
    if env:
        return float(env)
    return 1.13 if is_story() else 1.24


# 비트 tone → (감정 프리셋, 강도). promo=광고 톤(강), story=잔잔한 이야기 톤.
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
_TONE_EMOTION_STORY = {
    "hook": ("happy", 1.0),  # 친구가 말 거는 톤(들뜸 X)
    "problem": ("normal", 1.0),  # 담담한 관찰(우는 공감 X)
    "switch": ("normal", 1.0),
    "product": ("happy", 1.0),
    "usage": ("happy", 1.0),
    "result": ("happy", 1.05),  # 소소한 만족
    "cta": ("normal", 1.0),  # 나직한 권유
    "neutral": ("normal", 1.0),
}


def _tone_emotion(tone: str) -> tuple[str, float]:
    m = _TONE_EMOTION_STORY if is_story() else _TONE_EMOTION
    return m.get(tone, m["neutral"])


def _key() -> str:
    return (os.getenv("TYPECAST_API_KEY", "") or "").split("#")[0].strip()


def _voice_id_main() -> str:
    return (os.getenv("CLIPCART_TTS_VOICE_ID", "") or "").strip() or DEFAULT_VOICE_ID


def _voice_id_testimony() -> str:
    return (os.getenv("CLIPCART_TTS_VOICE_ID_TESTIMONY", "") or "").strip()


def _resolve_voice(voice: str) -> str:
    """대사 역할 → 실제 voice_id. 'testimony'는 증언용 보이스(설정 시), 아니면 메인."""
    if voice == "testimony":
        t = _voice_id_testimony()
        if t:
            return t
    return _voice_id_main()


@lru_cache(maxsize=1)
def _client():
    key = _key()
    if not key:
        return None
    try:
        from typecast import Typecast

        return Typecast(api_key=key)
    except Exception as e:  # noqa: BLE001
        print(f"  [typecast] init failed: {str(e)[:120]}")
        return None


@lru_cache(maxsize=16)
def _voice_meta(vid: str) -> dict:
    """voice_id의 (model, emotions) 메타. voices() 1회 조회 후 보이스별 캐시."""
    meta = {"voice_id": vid, "model": "ssfm-v30", "emotions": []}
    client = _client()
    if client is None:
        return meta
    try:
        for v in client.voices():
            if v.voice_id == vid:
                meta = {"voice_id": vid, "model": v.model, "emotions": list(v.emotions)}
                break
    except Exception:  # noqa: BLE001
        pass
    return meta


def available() -> bool:
    return _client() is not None


def _normalize(path: Path) -> None:
    """라우드니스 정규화 + atempo. story는 앞뒤 무음을 제거해 더 컴팩트·박진감 있게."""
    try:
        tmp = path.with_suffix(".norm.mp3")
        af = f"atempo={_tempo():.3f},loudnorm=I=-16:TP=-1.5:LRA=11"
        if is_story():
            # 클립 앞뒤 무음 제거(20ms만 남김) — 비트 전환을 바짝 붙여 간격을 줄인다
            trim = (
                "silenceremove=start_periods=1:start_silence=0.02:start_threshold=-45dB:detection=peak,"
                "areverse,"
                "silenceremove=start_periods=1:start_silence=0.02:start_threshold=-45dB:detection=peak,"
                "areverse"
            )
            af = f"{af},{trim}"
        subprocess.run(
            [ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(path),
             "-filter:a", af, "-ar", "44100", "-b:a", "160k", str(tmp)],
            capture_output=True, timeout=60,
        )
        if tmp.exists() and tmp.stat().st_size > 1000:
            tmp.replace(path)
    except Exception as e:  # noqa: BLE001
        print(f"  [typecast] normalize failed: {str(e)[:80]}")


def _cache_path(text: str, tone: str, vid: str) -> Path:
    # story는 무음 제거가 출력을 바꾸므로 캐시 키를 분리한다(promo 키는 불변)
    suffix = "|story-trim" if is_story() else ""
    h = hashlib.md5(f"{text}|{vid}|{tone}|{_tempo()}{suffix}".encode("utf-8")).hexdigest()[:16]
    return TTS_CACHE / f"tc_{h}.mp3"


def synth(text: str, tone: str, voice: str = "main", out: Path | None = None) -> tuple[Path, float] | None:
    """Typecast 합성 → (path, duration). 실패 시 None. voice: 'main'|'testimony'."""
    TTS_CACHE.mkdir(parents=True, exist_ok=True)
    vid = _resolve_voice(voice)
    cache = _cache_path(text, tone, vid)
    if cache.exists() and cache.stat().st_size > 1000:
        try:
            return cache, media_duration(cache)
        except Exception:  # noqa: BLE001
            cache.unlink(missing_ok=True)

    client = _client()
    if client is None:
        return None
    meta = _voice_meta(vid)
    emotion, intensity = _tone_emotion(tone)
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


def synth_or_edge(text: str, tone: str, voice: str = "main") -> tuple[Path, float]:
    """Typecast 우선, 실패 시 edge-tts 폴백. (path, duration) 보장."""
    res = synth(text, tone, voice=voice)
    if res is not None:
        return res
    # edge-tts 폴백
    from clipcart.video.tts import synthesize

    h = hashlib.md5(f"edge|{text}|{tone}".encode("utf-8")).hexdigest()[:16]
    path = TTS_CACHE / f"edge_{h}.mp3"
    synthesize(text, path, rate="+18%")
    return path, media_duration(path)
