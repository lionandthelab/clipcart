"""대본 스타일(레퍼토리) 선택·렌더 테스트.

대본이 매번 똑같아 AI스럽고 재미없다는 피드백(2026-06-14). 형식적인
전환·사용·결과·CTA 문장을 여러 스타일로 돌려 다양화하고, A/B용으로
특정 스타일을 강제할 수 있게 한다. 어색한 '{old_way}, 해보셨죠?'는
명사구에 자연스럽게 붙는 표현으로 교체한다.
"""

from __future__ import annotations

from clipcart.video.promo.script import SCRIPT_STYLES, pick_script_style, render_line


def _product(pid="CP1"):
    return {"product_id": pid, "price": 12900}


def test_pick_is_deterministic_per_product():
    a = pick_script_style(_product("CP1"))[0]
    b = pick_script_style(_product("CP1"))[0]
    assert a == b
    # 다른 상품은 (대체로) 다른 스타일 분포 — 최소한 호출이 안정적
    names = {pick_script_style(_product(f"CP{i}"))[0] for i in range(12)}
    assert len(names) >= 2  # 여러 스타일이 실제로 쓰인다


def test_env_force_selects_named_style(monkeypatch):
    monkeypatch.setenv("CLIPCART_SCRIPT_STYLE", "direct")
    name, style = pick_script_style(_product())
    assert name == "direct"
    assert style["name"] == "direct"


def test_env_force_unknown_falls_back(monkeypatch):
    monkeypatch.setenv("CLIPCART_SCRIPT_STYLE", "nonexistent")
    name, _ = pick_script_style(_product())
    assert name in {s["name"] for s in SCRIPT_STYLES}


def test_switch_line_is_natural_for_noun_oldway():
    # 명사구(기/방치)로 끝나는 old_way에 어색한 '해보셨죠?'를 붙이지 않는다
    for style in SCRIPT_STYLES:
        line = render_line(style["switch"], old_way="배수구 머리카락 손으로 빼기")
        assert "해보셨죠" not in line
        assert "배수구 머리카락 손으로 빼기" in line
        assert "{" not in line


def test_all_styles_render_every_variable_line():
    ctx = dict(old_way="책상 밑 선 뭉치 방치", usage="끼우기만 하면 됩니다",
               benefit="훨씬 깔끔해져요", downside="사이즈 확인은 필요해요", price=15900)
    for style in SCRIPT_STYLES:
        for key in ("switch", "usage", "result_tail", "cta"):
            out = render_line(style[key], **ctx)
            assert "{" not in out and out.strip()
        # 강조어는 전환 내레이션 안에 실제로 등장해야 슬램 타이밍이 맞는다
        assert style["switch_emphasis"] in render_line(style["switch"], **ctx)
