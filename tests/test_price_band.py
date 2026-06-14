"""가격대 env 조정 테스트.

기본 살림 꿀템은 저가대(4천~3.5만)지만, 프리미엄 아이템을 다루려면
실행 단위로 가격 상·하한을 올릴 수 있어야 한다(운영자 요청 2026-06-14).
"""

from __future__ import annotations

from clipcart.research.auto_select import price_band


def test_default_band(monkeypatch):
    monkeypatch.delenv("CLIPCART_PRICE_MIN", raising=False)
    monkeypatch.delenv("CLIPCART_PRICE_MAX", raising=False)
    assert price_band() == (4000, 35000)


def test_env_overrides_band(monkeypatch):
    monkeypatch.setenv("CLIPCART_PRICE_MIN", "30000")
    monkeypatch.setenv("CLIPCART_PRICE_MAX", "60000")
    assert price_band() == (30000, 60000)
