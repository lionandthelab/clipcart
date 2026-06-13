"""셀러 영상에서 중국어 자막이 적은 구간을 고르는 순수 함수 테스트.

OCR 없이: 프레임 하단 띠의 고주파(엣지) 에너지를 '텍스트 가능성'으로 보고,
점수가 가장 낮은(텍스트 적은) 시간 구간을 선택한다. 셀러 영상의 중국어
자막은 보통 하단에 박혀 있으므로 이 휴리스틱이 유효하다.
"""

from __future__ import annotations

import numpy as np

from clipcart.video.promo.clean import (
    pick_clean_windows,
    score_timeline,
    text_band_score,
)


def _uniform_frame():
    return np.full((400, 300, 3), 128, dtype=np.uint8)


def _frame_with_bottom_text():
    f = np.full((400, 300, 3), 128, dtype=np.uint8)
    # 하단 띠에 고대비 세로 줄무늬 — 글자 같은 고주파 엣지
    f[330:370, :, :] = 128
    f[330:370, ::6, :] = 255
    f[330:370, 3::6, :] = 0
    return f


def test_text_band_score_higher_for_text_like_bottom():
    assert text_band_score(_frame_with_bottom_text()) > text_band_score(_uniform_frame()) * 3


def test_score_timeline_samples_n_points():
    frames = {0.0: _uniform_frame(), 5.0: _frame_with_bottom_text()}

    def sample(t):
        # 가까운 키프레임 반환
        return _frame_with_bottom_text() if t >= 4.0 else _uniform_frame()

    scored = score_timeline(sample, duration=10.0, n=5)
    assert len(scored) == 5
    ts = [t for t, _ in scored]
    assert ts[0] >= 0.0 and ts[-1] <= 10.0
    # 뒤쪽(텍스트 구간) 점수가 앞쪽보다 높다
    assert scored[-1][1] > scored[0][1]


def test_pick_clean_windows_lands_on_low_score_region():
    scored = [(float(t), s) for t, s in zip(range(10), [9, 9, 5, 1, 0, 0, 1, 5, 9, 9])]
    wins = pick_clean_windows(scored, want=2.0, k=1, total=10.0)
    assert wins[0] == (4.0, 6.0)


def test_pick_clean_windows_returns_k_non_overlapping():
    scored = [(float(t), s) for t, s in zip(range(10), [9, 9, 5, 1, 0, 0, 1, 5, 9, 9])]
    wins = pick_clean_windows(scored, want=2.0, k=2, total=10.0)
    assert len(wins) == 2
    (s0, e0), (s1, e1) = sorted(wins)
    assert e0 <= s1  # 비겹침
    assert wins[0] == (4.0, 6.0)  # 가장 깨끗한 구간이 먼저


def test_pick_clean_windows_short_video_returns_whole():
    scored = [(0.0, 3.0), (1.0, 3.0)]
    wins = pick_clean_windows(scored, want=5.0, k=2, total=2.0)
    assert wins[0] == (0.0, 2.0)


def test_pick_clean_windows_wraps_when_fewer_distinct_than_k():
    # 표본이 빈약해도 k개를 항상 채운다(부족하면 가장 깨끗한 구간 재사용)
    scored = [(0.0, 1.0), (1.0, 0.0)]
    wins = pick_clean_windows(scored, want=1.0, k=2, total=2.0)
    assert len(wins) == 2
