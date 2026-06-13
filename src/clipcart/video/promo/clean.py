"""셀러 영상의 중국어 자막 회피 — OCR 없는 휴리스틱.

셀러 제품 영상은 보통 하단에 중국어 자막이 박혀 있다. 프레임 하단 띠의
고주파(엣지) 에너지를 '텍스트 가능성' 점수로 보고, 점수가 낮은(텍스트가
적은) 시간 구간을 골라 그 부분만 편집에 쓴다. numpy만 사용(무거운 OCR 없음).
"""

from __future__ import annotations

from typing import Callable

import numpy as np


# 셀러영상에서 크롭으로 지울 수 없는 중앙 영역 — 여기 글자가 있으면 그 시점은 버린다.
# 하단(0.75~)의 자막은 _seller_subclip 크롭이 처리하므로 점수에서 제외한다.
CENTER_BAND = (0.42, 0.74)


def text_band_score(frame: np.ndarray, band: tuple[float, float] = (0.78, 0.98)) -> float:
    """프레임 특정 띠의 엣지 밀도. 글자가 많을수록 높다."""
    if frame.ndim == 3:
        gray = frame.mean(axis=2)
    else:
        gray = frame.astype(np.float64)
    h = gray.shape[0]
    y0, y1 = int(h * band[0]), int(h * band[1])
    strip = gray[y0:y1]
    if strip.size == 0:
        return 0.0
    # 인접 픽셀 절대 차(수평+수직 그래디언트) 평균 — 글자 가장자리에서 커진다
    gx = np.abs(np.diff(strip, axis=1)).mean() if strip.shape[1] > 1 else 0.0
    gy = np.abs(np.diff(strip, axis=0)).mean() if strip.shape[0] > 1 else 0.0
    return float(gx + gy)


def score_timeline(
    sample_fn: Callable[[float], np.ndarray],
    duration: float,
    n: int = 12,
    band: tuple[float, float] = (0.78, 0.98),
) -> list[tuple[float, float]]:
    """[0, duration]을 n등분해 각 시점 프레임의 텍스트 점수를 매긴다."""
    n = max(1, n)
    out: list[tuple[float, float]] = []
    for i in range(n):
        t = duration * (i + 0.5) / n
        try:
            out.append((t, text_band_score(sample_fn(t), band)))
        except Exception:  # noqa: BLE001 — 프레임 디코드 실패는 최악 점수로
            out.append((t, float("inf")))
    return out


def _window_cost(scored: list[tuple[float, float]], s: float, e: float) -> float:
    inside = [sc for (t, sc) in scored if s <= t < e]
    if not inside:
        # 표본이 없으면 가장 가까운 표본으로 근사
        inside = [min(scored, key=lambda ts: abs(ts[0] - (s + e) / 2))[1]] if scored else [0.0]
    return float(sum(inside))


def pick_clean_windows(
    scored: list[tuple[float, float]], want: float, k: int, total: float
) -> list[tuple[float, float]]:
    """텍스트가 가장 적은 길이 `want`의 구간 k개(서로 겹치지 않게)."""
    want = min(want, total)
    if total <= want or not scored:
        return [(0.0, total)] * max(1, k)

    starts = sorted({min(max(t - want / 2, 0.0), total - want) for t, _ in scored} | {0.0})
    ranked = sorted(starts, key=lambda s: (_window_cost(scored, s, s + want), s))

    chosen: list[tuple[float, float]] = []
    for s in ranked:
        e = s + want
        if all(e <= cs or s >= ce for cs, ce in chosen):
            chosen.append((s, e))
            if len(chosen) == k:
                break
    # 비겹침으로 k개를 못 채우면 가장 깨끗한 구간을 재사용해 채운다
    while len(chosen) < k:
        chosen.append(chosen[0] if chosen else (0.0, want))
    return chosen
