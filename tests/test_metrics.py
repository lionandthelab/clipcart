"""성과 스냅샷 수집기 테스트.

YouTube 영상 통계(조회/좋아요/댓글)와 쿠팡 리포트(클릭/주문/커미션)를
subId로 조인해 영상 단위 성과 스냅샷을 만든다. subId가 없는 레거시
영상·채널 레벨 실적은 미귀속(unattributed)으로 합산한다.
"""

from __future__ import annotations

import json

from clipcart.analytics.collector import build_snapshot, fetch_video_stats, summarize


def _post(video_id, product_id, sub_id=None, title="t"):
    return {
        "post_id": video_id,
        "product_id": product_id,
        "platform": "youtube_shorts",
        "source": "coupang",
        "status": "PUBLISHED",
        "published_at": "2026-06-10T07:20:00+00:00",
        "title": title,
        "title_template": "{hook}",
        "sub_id": sub_id,
    }


STATS = {
    "vidA": {"views": 1200, "likes": 30, "comments": 5},
    "vidB": {"views": 300, "likes": 2, "comments": 0},
}


def test_build_snapshot_joins_reports_by_sub_id():
    posts = [_post("vidA", "CP111", "ss111"), _post("vidB", "CP222", "ss222")]
    clicks = [
        {"date": "20260610", "subId": "ss111", "click": 4},
        {"date": "20260611", "subId": "ss111", "click": 2},
        {"date": "20260611", "subId": "ss222", "click": 1},
    ]
    commission = [
        {"date": "20260611", "subId": "ss111", "commission": 299.0, "gmv": 9950.0, "order": 1},
    ]
    snap = build_snapshot(posts, STATS, clicks, commission, "2026-06-12T09:00:00", "20260605", "20260612")

    a = next(v for v in snap["videos"] if v["video_id"] == "vidA")
    assert a["views"] == 1200
    assert a["clicks"] == 6
    assert a["commission"] == 299.0
    assert a["orders"] == 1
    assert a["title_template"] == "{hook}"  # 템플릿별 성적 집계 키
    b = next(v for v in snap["videos"] if v["video_id"] == "vidB")
    assert b["clicks"] == 1
    assert b["commission"] == 0.0


def test_unattributed_rows_go_to_channel_totals():
    posts = [_post("vidA", "CP111", "ss111")]
    clicks = [
        {"date": "20260610", "subId": "", "click": 7},          # subId 없는 레거시 링크
        {"date": "20260610", "subId": "salrimshorts", "click": 2},  # 채널 레벨 subId
        {"date": "20260610", "subId": "ss111", "click": 1},
    ]
    commission = [{"date": "20260610", "subId": "", "commission": 617.0, "gmv": 20550.0, "order": 1}]
    snap = build_snapshot(posts, STATS, clicks, commission, "2026-06-12T09:00:00", "20260605", "20260612")

    assert snap["channel"]["clicks_total"] == 10
    assert snap["channel"]["unattributed_clicks"] == 9
    assert snap["channel"]["commission_total"] == 617.0
    assert snap["channel"]["unattributed_commission"] == 617.0


def test_bio_subid_clicks_attributed_to_profile_funnel():
    """bio<상품ID> 클릭은 프로필(채널설명) 퍼널 — 영상 고정댓글발 클릭과
    분리 측정하고, 진짜 미귀속(빈 subId)과도 구분한다."""
    posts = [_post("vidA", "CP884", "ss884")]
    clicks = [
        {"date": "d", "subId": "ss884", "click": 3},    # 영상 고정댓글발
        {"date": "d", "subId": "bio884", "click": 5},   # 프로필 bio 페이지발(같은 상품)
        {"date": "d", "subId": "", "click": 2},         # 진짜 미귀속(태그 없는 옛 링크)
    ]
    commission = [
        {"date": "d", "subId": "bio884", "commission": 500.0, "gmv": 16000.0, "order": 1},
    ]
    snap = build_snapshot(posts, STATS, clicks, commission,
                          "2026-06-12T09:00:00", "20260605", "20260612")

    a = next(v for v in snap["videos"] if v["video_id"] == "vidA")
    assert a["clicks"] == 3            # 영상발만 (bio 미포함)
    assert a["bio_clicks"] == 5        # 프로필발 분리 측정
    assert a["bio_commission"] == 500.0
    ch = snap["channel"]
    assert ch["clicks_total"] == 10                 # 전체 합산은 그대로
    assert ch["bio_clicks_total"] == 5              # 프로필 퍼널 채널 합
    assert ch["bio_commission_total"] == 500.0
    assert ch["unattributed_clicks"] == 2           # bio는 미귀속이 아님(빈 subId만)


def test_non_numeric_bio_prefix_not_counted_as_profile_funnel():
    """'bio'로 시작하지만 상품ID(숫자)가 아닌 subId는 프로필 퍼널이 아님.
    'biofilm','biopromo' 같은 임의 subId 오분류 방지(리뷰 발견)."""
    posts = [_post("vidA", "CP884", "ss884")]
    clicks = [
        {"date": "d", "subId": "bio884", "click": 5},    # 진짜 프로필발(bio<상품ID>)
        {"date": "d", "subId": "biofilm", "click": 9},   # 'bio'로 시작하나 상품ID 아님
    ]
    snap = build_snapshot(posts, STATS, clicks, [], "2026-06-12T09:00:00", "20260605", "20260612")
    ch = snap["channel"]
    assert ch["bio_clicks_total"] == 5
    assert ch["unattributed_clicks"] == 9   # biofilm은 미귀속으로 분류


def test_aliexpress_source_post_has_no_bio_attribution_even_with_cp_id():
    """방어적: 소스가 알리면 CP형 product_id라도 bio subId를 만들지 않는다
    (bio/page.py bio_sub_id와 동일 규칙)."""
    posts = [{**_post("vidA", "CP999", "ss999"), "source": "aliexpress"}]
    snap = build_snapshot(posts, STATS, [], [], "2026-06-12T09:00:00", "20260605", "20260612")
    assert snap["videos"][0]["bio_clicks"] is None


def test_aliexpress_video_has_null_bio_attribution():
    """알리는 subId 개념이 없어 bio 측정 불가 → None(0과 구분)."""
    posts = [{**_post("vidA", "AE777", "ss777"), "source": "aliexpress"}]
    snap = build_snapshot(posts, STATS, [], [], "2026-06-12T09:00:00", "20260605", "20260612")
    a = snap["videos"][0]
    assert a["bio_clicks"] is None
    assert a["bio_commission"] is None


def test_legacy_video_without_sub_id_has_null_attribution():
    posts = [_post("vidA", "CP111", sub_id=None)]
    snap = build_snapshot(posts, STATS, [], [], "2026-06-12T09:00:00", "20260605", "20260612")
    a = snap["videos"][0]
    assert a["views"] == 1200
    assert a["clicks"] is None  # 귀속 불가(0과 구분)
    assert a["commission"] is None


def test_parse_retention_report_maps_video_to_avg_view_pct():
    from clipcart.analytics.collector import parse_retention_report
    resp = {
        "columnHeaders": [
            {"name": "video"}, {"name": "views"},
            {"name": "averageViewPercentage"}, {"name": "averageViewDuration"},
        ],
        "rows": [
            ["vidA", 1200, 41.5, 12],
            ["vidB", 300, 18.0, 5],
        ],
    }
    r = parse_retention_report(resp)
    assert r["vidA"]["avg_view_pct"] == 41.5
    assert r["vidA"]["avg_view_duration"] == 12
    assert r["vidB"]["avg_view_pct"] == 18.0


def test_parse_retention_report_handles_empty():
    from clipcart.analytics.collector import parse_retention_report
    assert parse_retention_report({}) == {}
    assert parse_retention_report({"rows": []}) == {}


def test_fetch_retention_short_circuits_on_empty_ids():
    from clipcart.analytics.collector import fetch_retention
    assert fetch_retention([], "20260605", "20260612") == ({}, None)


def test_build_snapshot_attaches_retention_and_weighted_channel_avg():
    posts = [_post("vidA", "CP1", "s1"), _post("vidB", "CP2", "s2")]
    retention = {
        "vidA": {"avg_view_pct": 40.0, "avg_view_duration": 12},
        "vidB": {"avg_view_pct": 20.0, "avg_view_duration": 6},
    }
    snap = build_snapshot(posts, STATS, [], [], "t", "20260605", "20260612", retention=retention)
    a = next(v for v in snap["videos"] if v["video_id"] == "vidA")
    assert a["avg_view_pct"] == 40.0
    assert a["avg_view_duration"] == 12
    # 조회수 가중 평균: (40*1200 + 20*300) / 1500 = 36.0
    assert round(snap["channel"]["avg_view_pct"], 1) == 36.0


def test_build_snapshot_retention_none_when_absent():
    snap = build_snapshot([_post("vidA", "CP1", "s1")], STATS, [], [], "t", "20260605", "20260612")
    assert snap["videos"][0]["avg_view_pct"] is None
    assert snap["channel"]["avg_view_pct"] is None


def test_summarize_sorts_by_views_and_totals():
    posts = [_post("vidA", "CP111", "ss111"), _post("vidB", "CP222", "ss222")]
    snap = build_snapshot(posts, STATS, [{"date": "d", "subId": "ss222", "click": 3}], [],
                          "2026-06-12T09:00:00", "20260605", "20260612")
    s = summarize(snap)
    assert s["videos"][0]["video_id"] == "vidA"  # 조회수 내림차순
    assert s["totals"]["views"] == 1500
    assert s["totals"]["clicks"] == 3


def test_fetch_video_stats_parses_api_response(monkeypatch):
    import clipcart.analytics.collector as col

    class FakeResp:
        status_code = 200

        @staticmethod
        def json():
            return {
                "items": [
                    {"id": "vidA", "statistics": {"viewCount": "1200", "likeCount": "30", "commentCount": "5"}},
                    {"id": "vidB", "statistics": {"viewCount": "300"}},  # 좋아요 비공개 등 필드 누락
                ]
            }

        @staticmethod
        def raise_for_status():
            return None

    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["params"] = params
        return FakeResp()

    monkeypatch.setenv("YOUTUBE_API_KEY", "k")
    monkeypatch.setattr(col.requests, "get", fake_get)
    stats = fetch_video_stats(["vidA", "vidB"])
    assert stats["vidA"] == {"views": 1200, "likes": 30, "comments": 5}
    assert stats["vidB"] == {"views": 300, "likes": 0, "comments": 0}
    assert captured["params"]["id"] == "vidA,vidB"


def test_load_metrics_tolerates_empty_file(tmp_path, monkeypatch):
    import clipcart.storage as storage

    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    (tmp_path / "metrics.json").write_text("", encoding="utf-8")  # 현재 운영 상태 그대로
    assert storage.load_metrics() == []
    storage.save_metrics([{"collected_at": "x"}])
    assert json.loads((tmp_path / "metrics.json").read_text(encoding="utf-8"))[0]["collected_at"] == "x"


def test_consent_scopes_include_analytics_superset_of_refresh_scopes():
    # 동의 플로우는 리텐션 읽기 권한을 추가로 요청하되, 갱신용 SCOPES는 그대로여야
    # 기존 업로드 토큰 갱신이 invalid_scope로 깨지지 않는다.
    from clipcart.publishing.youtube import CONSENT_SCOPES, SCOPES
    assert set(SCOPES).issubset(set(CONSENT_SCOPES))
    assert any("yt-analytics" in s for s in CONSENT_SCOPES)
    assert not any("yt-analytics" in s for s in SCOPES)
