"""게시 직후 bio 자동 갱신 — 소프트페일 계약 테스트.

clipcart daily 직접 실행 시에도 게시 성공 후 bio가 따라오게 한다(운영자 요청
2026-06-18). 단 bio 갱신 실패가 게시 결과를 깨면 안 된다(게시는 이미 끝났음).
"""

from __future__ import annotations

import clipcart.pipeline.daily as daily


def test_refresh_bio_swallows_errors(monkeypatch):
    import clipcart.bio.page as page

    def boom():
        raise RuntimeError("bio 빌드 실패")

    monkeypatch.setattr(page, "build_bio_page", boom)
    # 예외가 새어나오면 안 된다
    daily._refresh_bio()


def test_refresh_bio_calls_build(monkeypatch):
    import clipcart.bio.page as page

    called = {}
    monkeypatch.setattr(page, "build_bio_page", lambda: called.setdefault("ok", True))
    daily._refresh_bio()
    assert called.get("ok") is True
