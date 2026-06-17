"""크로스 플랫폼 한글 폰트 해석.

윈도우(맑은 고딕)와 macOS(Apple SD Gothic Neo), 리눅스(나눔고딕)를 모두 지원한다.
Apple SD Gothic Neo는 TrueType Collection이라 가중치별 index가 필요하다
(0=Regular, 6=Bold). 윈도우 데일리(쿠팡)와 macOS 데일리(알리)가 같은 코드를 쓴다.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

# (path, index) — index는 ttc 가중치 선택용(ttf는 0)
_BOLD_CANDIDATES: list[tuple[str, int]] = [
    (r"C:\Windows\Fonts\malgunbd.ttf", 0),
    ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 6),  # Bold
    ("/System/Library/Fonts/Supplemental/AppleGothic.ttf", 0),
    ("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf", 0),
    ("/Library/Fonts/NanumGothicBold.ttf", 0),
]
_REGULAR_CANDIDATES: list[tuple[str, int]] = [
    (r"C:\Windows\Fonts\malgun.ttf", 0),
    ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 0),  # Regular
    ("/System/Library/Fonts/Supplemental/AppleGothic.ttf", 0),
    ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf", 0),
    ("/Library/Fonts/NanumGothic.ttf", 0),
]

# 디스플레이(팬시·초굵은 검은고딕) — 강조 슬램/제목/자막용. 레포 번들 우선, 없으면 볼드 폴백.
# 레포에 동봉(assets/fonts)하므로 윈도우/맥 데일리가 동일하게 사용한다.
_REPO_FONTS = Path(__file__).resolve().parents[3] / "assets" / "fonts"
_DISPLAY_CANDIDATES: list[tuple[str, int]] = [
    (str(_REPO_FONTS / "BlackHanSans-Regular.ttf"), 0),
    *_BOLD_CANDIDATES,
]

# 모던(깔끔·요즘 앱) 산세리프 — story 템플릿용. Pretendard(레포 동봉, OTF) 우선.
# SemiBold가 깔끔·모던 인상에 가장 잘 맞아 1순위. 없으면 시스템 볼드로 폴백,
# 강렬한 검은고딕(display)은 배제한다. (PIL은 .otf/.ttf 모두 로드)
_MODERN_CANDIDATES: list[tuple[str, int]] = [
    (str(_REPO_FONTS / "Pretendard-SemiBold.otf"), 0),
    (str(_REPO_FONTS / "Pretendard-Bold.otf"), 0),
    (str(_REPO_FONTS / "Pretendard-Medium.otf"), 0),
    (str(_REPO_FONTS / "Pretendard-Regular.otf"), 0),
    *_BOLD_CANDIDATES,
]

_CANDIDATES = {
    "bold": _BOLD_CANDIDATES,
    "regular": _REGULAR_CANDIDATES,
    "display": _DISPLAY_CANDIDATES,
    "modern": _MODERN_CANDIDATES,
}


@lru_cache(maxsize=4)
def _resolve(kind: str) -> tuple[str, int]:
    for path, index in _CANDIDATES.get(kind, _REGULAR_CANDIDATES):
        if Path(path).exists():
            return path, index
    raise RuntimeError("한글 폰트를 찾을 수 없음 (맑은 고딕 / Apple SD Gothic Neo / 나눔고딕)")


def load_font(
    size: int, bold: bool = True, display: bool = False, modern: bool = False
) -> ImageFont.FreeTypeFont:
    if modern:
        kind = "modern"
    elif display:
        kind = "display"
    elif bold:
        kind = "bold"
    else:
        kind = "regular"
    path, index = _resolve(kind)
    return ImageFont.truetype(path, size, index=index)
