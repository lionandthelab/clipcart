"""성과 분석 리포트 빌더 테스트.

metrics 스냅샷 + history를 소스·훅(title_template)·카테고리별로 집계하고,
클릭은 subId로 귀속된 것만 합산한다(미귀속은 채널 합산에 별도 표시).
조회수는 나이 편향이 적은 '중앙값'을 대표값으로 쓴다.
"""

from __future__ import annotations

from clipcart.analytics.report import build_report, render_text


def _snapshot():
    return {
        "window": {"start": "20260605", "end": "20260614"},
        "videos": [
            {"video_id": "a", "source": "coupang", "title_template": "{hook}",
             "script_style": "direct",
             "title": "A", "views": 2000, "likes": 10, "comments": 1,
             "sub_id": "s_a", "clicks": 5, "orders": 1, "commission": 300.0},
            {"video_id": "b", "source": "coupang", "title_template": "{hook}",
             "title": "B", "views": 1000, "likes": 4, "comments": 0,
             "sub_id": "s_b", "clicks": 1, "orders": 0, "commission": 0.0},
            {"video_id": "c", "source": "aliexpress", "title_template": "아직도 {old_way}? 이거 보세요",
             "title": "C", "views": 1500, "likes": 6, "comments": 1,
             "sub_id": None, "clicks": None, "orders": None, "commission": None},
            {"video_id": "z", "source": "coupang", "title_template": "{hook}",
             "title": "Z(통계없음)", "views": 0, "likes": 0, "comments": 0,
             "sub_id": "s_z", "clicks": None, "orders": None, "commission": None},
        ],
        "channel": {"views": 4500, "clicks_total": 12, "commission_total": 800.0,
                    "unattributed_clicks": 6, "unattributed_commission": 500.0},
    }


def _history():
    return [
        {"post_id": "a", "category": "정리/수납", "niche_keyword": "옷장 칸막이"},
        {"post_id": "b", "category": "욕실", "niche_keyword": "배수구 거름망"},
        {"post_id": "c", "category": "정리/수납", "niche_keyword": "케이블 정리"},
    ]


def test_totals_count_only_videos_with_views():
    r = build_report(_snapshot(), _history())
    assert r["totals"]["videos"] == 3  # views=0 인 z 제외
    assert r["totals"]["views"] == 4500
    assert r["totals"]["clicks_attributed"] == 6  # 5+1 (귀속분만)
    assert r["totals"]["commission_attributed"] == 300.0
    assert r["totals"]["unattributed_clicks"] == 6


def test_by_source_groups_and_sorts_by_median_views():
    r = build_report(_snapshot(), _history())
    src = {g["key"]: g for g in r["by_source"]}
    assert src["coupang"]["n"] == 2  # a,b (z 제외)
    assert src["coupang"]["views_median"] == 1500  # median(2000,1000)
    assert src["coupang"]["clicks"] == 6
    assert src["aliexpress"]["n"] == 1
    assert src["aliexpress"]["clicks"] is None  # 귀속 영상 없음 → None
    # 중앙값 내림차순 정렬
    assert [g["key"] for g in r["by_source"]] == ["coupang", "aliexpress"]


def test_by_hook_and_category_present():
    r = build_report(_snapshot(), _history())
    hooks = {g["key"]: g for g in r["by_hook"]}
    assert hooks["{hook}"]["n"] == 2
    cats = {g["key"]: g for g in r["by_category"]}
    assert cats["정리/수납"]["n"] == 2  # a,c
    assert cats["욕실"]["n"] == 1


def test_by_script_groups_style_and_missing():
    r = build_report(_snapshot(), _history())
    scripts = {g["key"]: g for g in r["by_script"]}
    assert scripts["direct"]["n"] == 1  # a
    assert scripts["(미기록)"]["n"] == 2  # b,c (script_style 없음)


def test_leaderboard_top_and_bottom():
    r = build_report(_snapshot(), _history())
    assert r["leaderboard"]["top"][0]["video_id"] == "a"  # 2000뷰
    assert r["leaderboard"]["bottom"][0]["video_id"] == "b"  # 1000뷰 (z 제외)


def test_render_text_is_readable_string():
    txt = render_text(build_report(_snapshot(), _history()))
    assert "소스" in txt and "훅" in txt and "카테고리" in txt
    assert "coupang" in txt
    assert isinstance(txt, str) and len(txt) > 100
