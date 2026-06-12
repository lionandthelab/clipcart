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

_CANDIDATES = {"bold": _BOLD_CANDIDATES, "regular": _REGULAR_CANDIDATES, "display": _DISPLAY_CANDIDATES}


@lru_cache(maxsize=4)
def _resolve(kind: str) -> tuple[str, int]:
    for path, index in _CANDIDATES.get(kind, _REGULAR_CANDIDATES):
        if Path(path).exists():
            return path, index
    raise RuntimeError("한글 폰트를 찾을 수 없음 (맑은 고딕 / Apple SD Gothic Neo / 나눔고딕)")


def load_font(size: int, bold: bool = True, display: bool = False) -> ImageFont.FreeTypeFont:
    kind = "display" if display else ("bold" if bold else "regular")
    path, index = _resolve(kind)
    return ImageFont.truetype(path, size, index=index)
