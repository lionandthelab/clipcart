"""원장-실제 업로드 동기화 테스트.

운영자가 영상을 비공개/삭제하면 그 게시는 더 이상 '업로드됨'이 아니다 —
history의 중복 차단·니치 잠금에서 제외하고(같은 제품·니치 재선정 가능),
posts 상태도 NOT_LIVE로 정정한다. 단 append-only 감사 기록은 보존(live
플래그 마킹, 삭제 아님).
"""

from __future__ import annotations

import clipcart.research.history as history
from clipcart.analytics.collector import sync_not_live


def _entries():
    return [
        {"post_id": "live1", "product_id": "CP1", "coupang_product_id": "1",
         "product_name": "배수구 거름망", "niche_keyword": "배수구", "date": "2026-06-10"},
        {"post_id": "dead1", "product_id": "CP2", "coupang_product_id": "2",
         "product_name": "가스레인지 틈새커버", "niche_keyword": "가스레인지", "date": "2026-06-11"},
    ]


def test_mark_not_live_flags_and_is_idempotent(monkeypatch):
    items = _entries()
    saved = {}
    monkeypatch.setattr(history, "load_history", lambda: items)
    monkeypatch.setattr(history, "_save", lambda x: saved.update(items=x))

    assert history.mark_not_live({"dead1"}) == 1
    dead = next(e for e in saved["items"] if e["post_id"] == "dead1")
    assert dead["live"] is False
    assert next(e for e in saved["items"] if e["post_id"] == "live1").get("live") is not False
    # 이미 마킹된 항목은 재마킹하지 않음
    assert history.mark_not_live({"dead1"}) == 0


def test_dedup_helpers_exclude_not_live(monkeypatch):
    items = _entries()
    items[1]["live"] = False
    monkeypatch.setattr(history, "load_history", lambda: items)

    assert history.used_coupang_ids() == {"1"}
    assert history.name_key("가스레인지 틈새커버") not in history.used_name_keys()
    assert "가스레인지" not in history.keyword_last_used()  # 니치 잠금 해제
    assert history.keyword_last_used() == {"배수구": "2026-06-10"}


def test_sync_not_live_corrects_posts_status():
    posts = [
        {"post_id": "live1", "platform": "youtube_shorts", "status": "PUBLISHED"},
        {"post_id": "dead1", "platform": "youtube_shorts", "status": "PUBLISHED"},
        {"post_id": "old", "platform": "youtube_shorts", "status": "REPLACED_PRIVATE"},
        {"post_id": "ig1", "platform": "instagram_reels", "status": "PUBLISHED"},
    ]
    updated, not_live = sync_not_live(posts, live_ids={"live1"})
    assert not_live == {"dead1"}
    by_id = {p["post_id"]: p for p in updated}
    assert by_id["dead1"]["status"] == "NOT_LIVE"
    assert by_id["live1"]["status"] == "PUBLISHED"
    assert by_id["old"]["status"] == "REPLACED_PRIVATE"  # 이미 비공개 계열은 불변
    assert by_id["ig1"]["status"] == "PUBLISHED"  # 타 플랫폼 불변


def test_dead_video_ids_covers_already_replaced_posts():
    # REPLACED_PRIVATE 등 비공개 계열 게시의 history 항목도 잠금 해제 대상 —
    # 조회한 전체 ID 기준으로 죽은 ID를 계산한다(빈 live는 가드).
    from clipcart.analytics.collector import dead_video_ids

    assert dead_video_ids(["a", "b", "c"], {"a"}) == {"b", "c"}
    assert dead_video_ids(["a", "b"], set()) == set()


def test_sync_not_live_guards_against_empty_live_set():
    # API 이상으로 전부 죽은 것처럼 보이면 동기화를 건너뛴다 —
    # 원장 대량 해제는 중복 업로드 사고로 이어진다.
    posts = [
        {"post_id": "a", "platform": "youtube_shorts", "status": "PUBLISHED"},
        {"post_id": "b", "platform": "youtube_shorts", "status": "PUBLISHED"},
    ]
    updated, not_live = sync_not_live(posts, live_ids=set())
    assert not_live == set()
    assert all(p["status"] == "PUBLISHED" for p in updated)
