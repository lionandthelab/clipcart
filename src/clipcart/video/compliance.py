"""게시 전 자동 컴플라이언스 검사 (전자동 모드의 하드 게이트)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from clipcart.aliexpress import ALIEXPRESS_DISCLOSURE
from clipcart.coupang import COUPANG_DISCLOSURE
from clipcart.video.ff import media_duration, video_resolution

# 소스별 의무 고지 전체 집합 — 다른 소스 고지가 섞이면 허위 고지로 차단한다
_ALL_DISCLOSURES = {COUPANG_DISCLOSURE, ALIEXPRESS_DISCLOSURE}

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
    # 허위 사용 후기 차단(CLAUDE.md 1.2) — 실제 안 써본 제품을 써본 듯 단정하는 표현.
    # story 템플릿이 1인칭 화법을 늘리므로 하드게이트로 강제한다.
    "제가 써보니",
    "한 달 써본",
    "내돈내산",
    "효과 봤어요",
    "직접 사용",
    # 공정위 2024-12 개정: 조건부 고지 표현 금지 (확정형 '제공받습니다'만 인정)
    "수수료를 받을 수 있습니다",
    "제공받을 수 있습니다",
]


# 금지어 → 중립 표현 치환. 우리가 생성하는 문구(상품명/니치/카피)에 섞인 과장어를
# 게시 차단(하드게이트) 대신 정화한다. 실데이터·고지·수치는 건드리지 않는다.
# 더 구체적인 표현을 먼저 둬서 부분치환 충돌을 피한다.
_SANITIZE_REPLACEMENTS: list[tuple[str, str]] = [
    ("곰팡이 완전 제거", "곰팡이 관리"),
    ("세균 박멸", "세균 관리"),
    ("효과 보장", "도움"),
    ("수수료를 받을 수 있습니다", "수수료를 제공받습니다"),
    ("제공받을 수 있습니다", "제공받습니다"),
    ("품절 전에", ""),
    # '직접 써봤'은 정화하지 않는다 — 무근거 전언('써본 사람들은')으로 바꿔 게이트를
    #  우회시키던 구멍을 닫는다. 그대로 두면 BANNED_EXPRESSIONS가 차단(허위후기 방지).
    ("평생", "계속"),
    ("무조건", ""),
    ("100%", ""),
    ("완벽", "깔끔"),
    ("박멸", "제거"),
    ("최저가", "가성비"),
    ("인생템", "추천템"),
    ("역대급", "인기"),
]


def sanitize_text(text: str) -> str:
    """우리가 만든 문구에서 금지 표현만 중립 표현으로 정화(차단 예방). 빈자리 공백 정리."""
    if not text:
        return text
    import re

    for bad, good in _SANITIZE_REPLACEMENTS:
        text = text.replace(bad, good)
    return re.sub(r"\s{2,}", " ", text).strip()


def check_texts(creative: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    affiliate_url = creative.get("affiliate_url", "") or ""
    pinned = creative.get("pinned_comment", "") or ""
    description = creative.get("description", "")

    texts = [creative.get("title", ""), description, pinned]
    texts += [s.get("narration", "") + " " + s.get("caption", "") for s in creative.get("scenes", [])]
    blob = "\n".join(texts)
    # 제휴 URL은 광고문구가 아니므로 금지어 스캔에서 제외 — 폴백 raw URL에 '100%'
    # 같은 ASCII 금지어가 부분일치해 정상 링크가 오탐 차단되는 것을 막는다.
    if affiliate_url:
        blob = blob.replace(affiliate_url, "")
    for banned in BANNED_EXPRESSIONS:
        if banned in blob:
            issues.append(f"금지 표현 포함: '{banned}'")

    # 퍼널 무결성: 클릭/구매로 이어질 제휴 링크가 실제로 박혀 있어야 한다.
    # 쿠팡 productUrl 없음·알리 promotion_link 빈값 등으로 affiliate_url이 비면
    # 링크 없는 영상이 게시돼 클릭 0으로 직결되므로 하드 차단한다.
    if not affiliate_url.startswith("http"):
        issues.append("제휴 링크 누락 — 클릭/구매 귀속 불가, 게시 차단")
    else:
        if affiliate_url not in pinned:
            issues.append("고정댓글에 제휴 링크 누락 — 첫 줄 링크 직노출 요건")
        if affiliate_url not in description:
            issues.append("설명란에 제휴 링크 누락")

    # creative가 선언한 소스별 고지를 기준으로 검사(쿠팡/알리 공통). 미지정이면 쿠팡 고지.
    required = creative.get("disclosure") or COUPANG_DISCLOSURE
    if required not in description:
        issues.append("설명란에 어필리에이트 의무 고지 누락")
    elif description.find(required) > 250:
        issues.append("고지 문구가 설명란 첫 부분(더보기 위)에 없음 — 공정위 요건")
    for foreign in _ALL_DISCLOSURES - {required}:
        if foreign and foreign in description:
            issues.append("다른 소스의 어필리에이트 고지 혼입 — 허위 고지")
    scenes = creative.get("scenes", [])
    if not any(s.get("disclosure") for s in scenes):
        issues.append("영상 내 고지 장면 누락")
    # 공정위: 동영상은 시작·끝에 표시 — '끝부분만 표기는 불인정'. 첫 장면(훅)에
    # 고지가 없으면 시작 고지 누락으로 차단(과거엔 '아무 장면이든 보유'만 검사했음).
    elif not (scenes and scenes[0].get("disclosure")):
        issues.append("영상 시작 부분 고지 누락 — 공정위 시작·끝 표시 요건('끝부분만 표기 불인정')")
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
