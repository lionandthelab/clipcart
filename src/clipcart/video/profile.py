"""흥행 쇼츠 모방 포맷 프로파일.

리서치 결과는 data/format_profile.json 으로 저장되며 기본값을 덮어쓴다.
"""

from __future__ import annotations

import json
from typing import Any

from clipcart.config import DATA_DIR

PROFILE_FILE = DATA_DIR / "format_profile.json"

DEFAULT_PROFILE: dict[str, Any] = {
    "title_templates": [
        "{hook}",
        "아직도 {old_way}? 이거 보세요",
        "{title_keyword}, 단점까지 보고 사세요",
        "{problem_short} 이걸로 끝내는 법",
        "{price_won}원으로 {problem_short} 해결한 후기",
        "{title_keyword} 쓰기 전엔 몰랐던 것",
    ],
    # 공정위: 고지는 설명란 첫 부분(더보기 위)에 — 끝부분만 표기는 불인정
    "description_template": (
        "{hook}\n"
        "{disclosure}\n\n"
        "이런 분께 추천해요: {target}\n\n"
        "좋은 점: {benefit_short}\n"
        "아쉬운 점: {downside}\n\n"
        "제품 링크: {affiliate_url}\n\n"
        "{hashtags}"
    ),
    "hashtags": ["#살림템", "#생활꿀템", "#자취템", "#살림해결소", "#shorts"],
    "tags": ["살림템", "생활꿀템", "자취템", "주방템", "청소템", "쿠팡추천", "살림해결소"],
    "subtitle_style": {
        "primary_color": "#FFFFFF",
        "highlight_color": "#FFE14D",
        "outline": "#000000",
        "position": "lower-center",
    },
    "tts_voice": "ko-KR-SunHiNeural",
    "tts_rate": "+12%",
    "target_length_seconds": 33,
    "posting_time_kst": "08:30",
    "thumbnail_recipe": "product photo + 2-line bold hook text, yellow highlight on key word",
}


def load_profile() -> dict[str, Any]:
    profile = dict(DEFAULT_PROFILE)
    if PROFILE_FILE.exists():
        try:
            saved = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
            for key, value in saved.items():
                if value:
                    profile[key] = value
        except Exception:
            pass
    return profile
