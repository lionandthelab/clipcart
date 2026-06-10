"""크로스 플랫폼 한글 폰트 로더 테스트."""

from __future__ import annotations

from clipcart.video.fonts import load_font


def test_load_bold_and_regular_return_fonts():
    bold = load_font(40, bold=True)
    reg = load_font(40, bold=False)
    # PIL FreeTypeFont — 한글 렌더 가능한 폰트가 해석돼야 한다(미해석 시 RuntimeError)
    assert bold.getname()[0]
    assert reg.getname()[0]
    # 한글 글리프 폭이 0이 아니어야(폰트가 한글을 담고 있어야)
    assert bold.getbbox("배수구")[2] > 0
