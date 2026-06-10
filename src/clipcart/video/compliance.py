"""게시 전 자동 컴플라이언스 검사 (전자동 모드의 하드 게이트)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from clipcart.coupang import COUPANG_DISCLOSURE
from clipcart.video.ff import media_duration, video_resolution

BANNED_EXPRESSIONS = [
    "무조건",
    "100%",
    "완벽",
    "평생",
    "세균 박멸",
    "박멸",
    "곰팡이 완전 제거",
    "효과 보장",
    "최저가",
    "직접 써봤",
    "인생템",
    "역대급",
    "품절 전에",
    # 공정위 2024-12 개정: 조건부 고지 표현 금지 (확정형 '제공받습니다'만 인정)
    "수수료를 받을 수 있습니다",
    "제공받을 수 있습니다",
]


def check_texts(creative: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    texts = [creative.get("title", ""), creative.get("description", "")]
    texts += [s.get("narration", "") + " " + s.get("caption", "") for s in creative.get("scenes", [])]
    blob = "\n".join(texts)
    for banned in BANNED_EXPRESSIONS:
        if banned in blob:
            issues.append(f"금지 표현 포함: '{banned}'")
    description = creative.get("description", "")
    # creative가 선언한 소스별 고지를 기준으로 검사(쿠팡/알리 공통). 미지정이면 쿠팡 고지.
    required = creative.get("disclosure") or COUPANG_DISCLOSURE
    if required not in description:
        issues.append("설명란에 어필리에이트 의무 고지 누락")
    elif description.find(required) > 250:
        issues.append("고지 문구가 설명란 첫 부분(더보기 위)에 없음 — 공정위 요건")
    if not any(s.get("disclosure") for s in creative.get("scenes", [])):
        issues.append("영상 내 고지 장면 누락")
    if len(creative.get("title", "")) > 100:
        issues.append("제목 100자 초과")
    return issues


def check_video(path: Path) -> list[str]:
    issues: list[str] = []
    if not path.exists() or path.stat().st_size < 100_000:
        return [f"영상 파일 이상: {path}"]
    duration = media_duration(path)
    if duration > 60:
        issues.append(f"영상 길이 {duration:.1f}s — Shorts 60초 초과")
    if duration < 15:
        issues.append(f"영상 길이 {duration:.1f}s — 너무 짧음")
    w, h = video_resolution(path)
    if w >= h:
        issues.append(f"세로 영상 아님: {w}x{h}")
    return issues
