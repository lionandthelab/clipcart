"""edge-tts 한국어 내레이션 합성."""

from __future__ import annotations

import asyncio
from pathlib import Path

import edge_tts


async def _synth_one(text: str, path: Path, voice: str, rate: str) -> None:
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
    await communicate.save(str(path))


def synthesize(text: str, path: Path, voice: str = "ko-KR-SunHiNeural", rate: str = "+12%") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(_synth_one(text, path, voice, rate))
    if not path.exists() or path.stat().st_size < 1000:
        raise RuntimeError(f"TTS 합성 실패: {text[:30]}")
    return path
