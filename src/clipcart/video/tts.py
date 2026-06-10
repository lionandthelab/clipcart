"""edge-tts 한국어 내레이션 합성 (단어 타이밍 포함)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import edge_tts


async def _synth_one(text: str, path: Path, voice: str, rate: str, pitch: str) -> None:
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch)
    await communicate.save(str(path))


def synthesize(
    text: str,
    path: Path,
    voice: str = "ko-KR-SunHiNeural",
    rate: str = "+12%",
    pitch: str = "+0Hz",
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(_synth_one(text, path, voice, rate, pitch))
    if not path.exists() or path.stat().st_size < 1000:
        raise RuntimeError(f"TTS 합성 실패: {text[:30]}")
    return path


async def _stream(text: str, voice: str, rate: str, pitch: str):
    audio = bytearray()
    words: list[dict] = []
    sents: list[dict] = []
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch)
    async for chunk in communicate.stream():
        ctype = chunk["type"]
        if ctype == "audio":
            audio.extend(chunk["data"])
        elif ctype == "WordBoundary":
            words.append({"text": chunk["text"], "start": chunk["offset"] / 1e7, "dur": chunk["duration"] / 1e7})
        elif ctype == "SentenceBoundary":
            sents.append({"start": chunk["offset"] / 1e7, "dur": chunk["duration"] / 1e7})
    return bytes(audio), words, sents


def _distribute(text: str, sents: list[dict], total: float) -> list[dict]:
    """문장 구간(있으면) 안에서 글자 수 비례로 단어 시작 시각 추정.

    한국어 음성은 WordBoundary를 안 주고 SentenceBoundary만 주는 경우가 많아
    실제 발화 시작/끝(span)을 잡은 뒤 그 안에 토큰을 글자 수로 배분한다.
    """
    tokens = text.split()
    if not tokens:
        return []
    if sents:
        span_start = max(sents[0]["start"], 0.0)
        span_end = min(sents[-1]["start"] + sents[-1]["dur"], total)
    else:
        span_start, span_end = 0.05, total
    if span_end <= span_start:
        span_end = span_start + max(total, 1.0)
    span = span_end - span_start
    weights = [len(tok) + 1 for tok in tokens]
    total_w = sum(weights)
    out: list[dict] = []
    cum = 0
    for tok, w in zip(tokens, weights):
        start = span_start + span * (cum / total_w)
        cum += w
        nxt = span_start + span * (cum / total_w)
        out.append({"text": tok, "start": start, "dur": max(nxt - start, 0.05)})
    return out


def synthesize_marks(
    text: str,
    path: Path,
    voice: str = "ko-KR-SunHiNeural",
    rate: str = "+12%",
    pitch: str = "+0Hz",
) -> list[dict]:
    """오디오 저장 + 단어별 {text,start,dur}(초). WordBoundary 없으면 문장 구간 기반 추정."""
    from clipcart.video.ff import media_duration

    path.parent.mkdir(parents=True, exist_ok=True)
    audio, words, sents = asyncio.run(_stream(text, voice, rate, pitch))
    if len(audio) < 1000:
        raise RuntimeError(f"TTS 합성 실패: {text[:30]}")
    path.write_bytes(audio)
    if words:
        return words
    return _distribute(text, sents, media_duration(path))
