"""저작권 위험 없는 효과음 생성 (ffmpeg lavfi 합성, 캐시)."""

from __future__ import annotations

from pathlib import Path

from clipcart.config import PROJECT_ROOT
from clipcart.video.ff import run_ffmpeg

SFX_DIR = PROJECT_ROOT / "tools" / "sfx"


def _gen(name: str, lavfi: str, af: str) -> Path:
    out = SFX_DIR / name
    if out.exists():
        return out
    SFX_DIR.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(["-f", "lavfi", "-i", lavfi, "-af", af, "-ar", "44100", "-ac", "2", str(out)], timeout=60)
    return out


def whoosh() -> Path:
    # 짧은 노이즈 스윕 — 컷 전환 타격감
    return _gen(
        "whoosh.wav",
        "anoisesrc=d=0.45:c=pink:a=0.9",
        "highpass=f=250,lowpass=f=7000,afade=t=in:d=0.04,afade=t=out:st=0.12:d=0.32,volume=0.5",
    )


def pop() -> Path:
    # 키워드/가격 등장 '톡'
    return _gen(
        "pop.wav",
        "sine=frequency=1100:duration=0.09",
        "afade=t=out:st=0.02:d=0.07,volume=0.45",
    )


def riser() -> Path:
    # 훅 도입 상승 처프
    return _gen(
        "riser.wav",
        "aevalsrc='0.6*sin(2*PI*(180+300*t)*t)':d=0.7:s=44100",
        "afade=t=in:d=0.1,afade=t=out:st=0.45:d=0.25,volume=0.4",
    )


def thud() -> Path:
    # 단점/마무리 저음 임팩트
    return _gen(
        "thud.wav",
        "sine=frequency=140:duration=0.25",
        "afade=t=out:st=0.05:d=0.2,volume=0.5",
    )
