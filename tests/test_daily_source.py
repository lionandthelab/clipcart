"""데일리 파이프라인의 소스별 중복-게시 스코핑 테스트.

같은 채널에 쿠팡(아침)·알리(저녁)가 따로 올라가므로, '오늘 이미 게시'
판정은 소스별로 분리돼야 한다(아침 쿠팡 게시가 저녁 알리 실행을 막으면 안 됨).
"""

from __future__ import annotations

from datetime import date

import clipcart.pipeline.daily as daily


def _post(source, platform="youtube_shorts", today=True):
    when = (date.today().isoformat() + "T19:00:00") if today else "2000-01-01T00:00:00"
    return {"platform": platform, "source": source, "published_at": when, "post_url": "u"}


def test_coupang_post_does_not_block_aliexpress(monkeypatch):
    monkeypatch.setattr(daily, "load_posts", lambda: [_post("coupang")])
    assert daily._already_posted_today("aliexpress") is None
    assert daily._already_posted_today("coupang") is not None


def test_aliexpress_post_blocks_only_aliexpress(monkeypatch):
    monkeypatch.setattr(daily, "load_posts", lambda: [_post("aliexpress")])
    assert daily._already_posted_today("aliexpress") is not None
    assert daily._already_posted_today("coupang") is None


def test_legacy_post_without_source_counts_as_coupang(monkeypatch):
    legacy = {"platform": "youtube_shorts", "published_at": date.today().isoformat() + "T07:20:00"}
    monkeypatch.setattr(daily, "load_posts", lambda: [legacy])
    assert daily._already_posted_today("coupang") is not None
    assert daily._already_posted_today("aliexpress") is None


def test_old_post_does_not_block_today(monkeypatch):
    monkeypatch.setattr(daily, "load_posts", lambda: [_post("aliexpress", today=False)])
    assert daily._already_posted_today("aliexpress") is None
