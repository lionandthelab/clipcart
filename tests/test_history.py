"""업로드 히스토리 원장의 소스별 중복 ID 분리 테스트."""

from __future__ import annotations

from clipcart.research import history


def test_used_ids_partition_by_source(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "HISTORY_FILE", tmp_path / "history.json")
    history.record(
        {"post_id": "p1", "coupang_product_id": "C1", "product_name": "쿠팡상품",
         "niche_keyword": "배수구 거름망 스테인리스", "date": "2026-06-10"}
    )
    history.record(
        {"post_id": "p2", "aliexpress_product_id": "A1", "product_name": "알리상품",
         "niche_keyword": "키보드 청소 젤", "date": "2026-06-09"}
    )

    assert history.used_coupang_ids() == {"C1"}
    assert history.used_aliexpress_ids() == {"A1"}
    # 이름 중복차단은 소스 공통 (다른 판매자의 동일 상품도 차단)
    assert history.name_key("알리상품") in history.used_name_keys()
    # 니치 마지막 사용일은 두 소스에 걸쳐 집계 (같은 문제 반복 방지)
    assert history.keyword_last_used()["배수구 거름망 스테인리스"] == "2026-06-10"
