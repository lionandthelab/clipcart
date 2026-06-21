"""썸네일 비주얼 변형 테스트 — 제품마다 다른 색·레이아웃으로 '다 똑같다' 방지."""

from __future__ import annotations

from PIL import Image

from clipcart.video.frames import compose_thumbnail


def _img():
    return Image.new("RGB", (900, 900), (130, 120, 110))


def test_variant_param_changes_thumbnail_output(tmp_path):
    data = []
    for v in range(6):
        out = compose_thumbnail(_img(), "큰 훅 문구", "서브 문구", tmp_path / f"t{v}.jpg", variant=v)
        assert out.exists()
        data.append(out.read_bytes())
    # 변형마다 결과가 충분히 다르다(색·레이아웃 차이)
    assert len(set(data)) >= 4


def test_variant_wraps_out_of_range(tmp_path):
    # thumb_variant는 큰 정수(해시 mod) — 범위를 벗어나도 안전하게 wrap
    out = compose_thumbnail(_img(), "훅", "서브", tmp_path / "big.jpg", variant=719)
    assert out.exists()
