"""성과 분석 리포트 — metrics 스냅샷을 소스·훅·카테고리별로 집계.

조회수는 나이 편향이 적은 중앙값을 대표값으로 쓰고, 클릭/커미션은 subId로
영상에 귀속된 것만 합산한다(미귀속분은 채널 합산에 별도 표시). 순수 함수라
테스트가 쉽고, clipcart analyze가 이를 텍스트로 렌더한다.
"""

from __future__ import annotations

import statistics
from typing import Any, Callable


def _median(xs: list[int]) -> int:
    return int(round(statistics.median(xs))) if xs else 0


def _attr_sum(videos: list[dict[str, Any]], field: str) -> int | float | None:
    """subId로 귀속된 값만 합산. 귀속 영상이 하나도 없으면 None."""
    vals = [v[field] for v in videos if v.get("sub_id") and v.get(field) is not None]
    return sum(vals) if vals else None


def _median_view_pct(videos: list[dict[str, Any]]) -> float | None:
    """시청 유지율 중앙값(유지율 있는 영상만). 평균은 쇼츠 루프/API 글리치 이상치에
    오염되므로(한 영상 3144% 실측) 중앙값으로 강건하게 집계한다. 없으면 None."""
    vals = [v["avg_view_pct"] for v in videos
            if v.get("avg_view_pct") is not None and v.get("views")]
    return round(statistics.median(vals), 1) if vals else None


def _group(videos: list[dict[str, Any]], keyfn: Callable[[dict], str]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict]] = {}
    for v in videos:
        groups.setdefault(keyfn(v), []).append(v)
    out = []
    for key, vs in groups.items():
        views = [v["views"] for v in vs]
        out.append(
            {
                "key": key,
                "n": len(vs),
                "views_median": _median(views),
                "views_mean": int(round(sum(views) / len(vs))),
                "views_total": sum(views),
                "clicks": _attr_sum(vs, "clicks"),
                "commission": _attr_sum(vs, "commission"),
                "avg_view_pct": _median_view_pct(vs),
            }
        )
    return sorted(out, key=lambda g: g["views_median"], reverse=True)


def build_report(snapshot: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
    """스냅샷 + history(카테고리/니치 조인)를 다차원으로 집계한 리포트."""
    hist_by_post = {h.get("post_id"): h for h in history}
    # 통계 0(막 올라간 영상)은 분석에서 제외
    videos = [v for v in snapshot.get("videos", []) if v.get("views", 0) > 0]
    for v in videos:
        h = hist_by_post.get(v["video_id"], {})
        v["_category"] = h.get("category") or "(미상)"
        v["_niche"] = h.get("niche_keyword") or "(미상)"

    ch = snapshot.get("channel", {})
    report = {
        "window": snapshot.get("window", {}),
        "totals": {
            "videos": len(videos),
            "views": ch.get("views", sum(v["views"] for v in videos)),
            "clicks_attributed": _attr_sum(videos, "clicks") or 0,
            "commission_attributed": _attr_sum(videos, "commission") or 0,
            "bio_clicks": ch.get("bio_clicks_total", 0),
            "bio_commission": ch.get("bio_commission_total", 0),
            "unattributed_clicks": ch.get("unattributed_clicks", 0),
            "unattributed_commission": ch.get("unattributed_commission", 0),
            "avg_view_pct": ch.get("avg_view_pct"),
            "aliexpress_orders": ch.get("aliexpress_orders_count", 0),
            "aliexpress_commission": ch.get("aliexpress_commission", 0),
        },
        "by_source": _group(videos, lambda v: v.get("source", "coupang")),
        "by_hook": _group(videos, lambda v: v.get("title_template") or "(미기록)"),
        "by_script": _group(videos, lambda v: v.get("script_style") or "(미기록)"),
        "by_category": _group(videos, lambda v: v["_category"]),
        "by_niche": _group(videos, lambda v: v["_niche"]),
        "leaderboard": {
            "top": [
                {"video_id": v["video_id"], "title": v.get("title", ""), "views": v["views"],
                 "clicks": v.get("clicks"), "source": v.get("source")}
                for v in sorted(videos, key=lambda v: v["views"], reverse=True)[:8]
            ],
            "bottom": [
                {"video_id": v["video_id"], "title": v.get("title", ""), "views": v["views"],
                 "clicks": v.get("clicks"), "source": v.get("source")}
                for v in sorted(videos, key=lambda v: v["views"])[:5]
            ],
        },
    }
    return report


def _fmt_clicks(c: int | float | None) -> str:
    return "-" if c is None else f"{c:g}"


def _fmt_pct(p: float | None) -> str:
    return "-" if p is None else f"{p:g}%"


def _render_groups(title: str, groups: list[dict[str, Any]]) -> list[str]:
    lines = [f"### {title} — 조회 중앙값 / 유지율 / 클릭(귀속)"]
    for g in groups:
        lines.append(
            f"  {g['views_median']:>5}  유지율={_fmt_pct(g.get('avg_view_pct')):>5}  "
            f"n={g['n']:<2} 클릭={_fmt_clicks(g['clicks']):>4}  {g['key']}"
        )
    return lines


def render_text(report: dict[str, Any]) -> str:
    t = report["totals"]
    w = report.get("window", {})
    lines = [
        f"성과 분석  ({w.get('start','?')}~{w.get('end','?')})",
        f"  영상 {t['videos']}편 · 누적 {t['views']:,}뷰 · 시청 유지율(중앙값) "
        f"{_fmt_pct(t['avg_view_pct'])} · "
        f"귀속클릭 {t['clicks_attributed']:g} · 귀속커미션 {t['commission_attributed']:g}원",
        f"  프로필발(bio): 클릭 {t['bio_clicks']:g} · 커미션 {t['bio_commission']:g}원 "
        f"(채널설명·고정프로필 링크 경유)",
        f"  알리 전환: 주문 {t['aliexpress_orders']:g}건 · 추정커미션 {t['aliexpress_commission']:g} "
        f"(알리 주문 API 실측, 채널 레벨)",
        f"  채널 미귀속: 클릭 {t['unattributed_clicks']:g} · 커미션 {t['unattributed_commission']:g}원 "
        f"(subId 이전 영상들)",
        "",
    ]
    lines += _render_groups("소스", report["by_source"]) + [""]
    lines += _render_groups("훅 템플릿", report["by_hook"]) + [""]
    lines += _render_groups("대본 말투", report["by_script"]) + [""]
    lines += _render_groups("카테고리", report["by_category"]) + [""]
    lines.append("### 조회 상위")
    for v in report["leaderboard"]["top"]:
        lines.append(f"  {v['views']:>5}뷰  클릭={_fmt_clicks(v['clicks']):>4}  [{(v.get('source') or '')[:3]}] {v['title'][:32]}")
    lines.append("### 조회 하위")
    for v in report["leaderboard"]["bottom"]:
        lines.append(f"  {v['views']:>5}뷰  클릭={_fmt_clicks(v['clicks']):>4}  [{(v.get('source') or '')[:3]}] {v['title'][:32]}")
    return "\n".join(lines)
