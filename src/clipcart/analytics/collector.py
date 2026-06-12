"""성과 스냅샷 수집기.

YouTube 영상 통계와 쿠팡 파트너스 리포트를 영상별 subId로 조인해
data/metrics.json에 스냅샷을 누적한다. 조회수만 높고 클릭이 없는
니치를 걸러내는 성과 루프(CLAUDE.md Step 7/8)의 데이터 기반.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests

from clipcart.coupang import report_clicks, report_commission, report_orders
from clipcart.storage import load_metrics, load_posts, save_metrics

YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


def fetch_video_stats(video_ids: list[str]) -> dict[str, dict[str, int]]:
    """YouTube Data API(API 키)로 공개 영상 통계 조회. 50개씩 배치."""
    api_key = os.getenv("YOUTUBE_API_KEY", "")
    if not api_key:
        raise RuntimeError("YOUTUBE_API_KEY 없음 (.env)")
    stats: dict[str, dict[str, int]] = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        resp = requests.get(
            YOUTUBE_VIDEOS_URL,
            params={"part": "statistics", "id": ",".join(batch), "key": api_key},
            timeout=30,
        )
        resp.raise_for_status()
        for item in resp.json().get("items", []):
            s = item.get("statistics", {})
            stats[item["id"]] = {
                "views": int(s.get("viewCount", 0)),
                "likes": int(s.get("likeCount", 0)),
                "comments": int(s.get("commentCount", 0)),
            }
    return stats


def _sum_by_sub_id(rows: list[dict[str, Any]], field: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in rows:
        key = row.get("subId") or ""
        out[key] = out.get(key, 0) + (row.get(field) or 0)
    return out


def build_snapshot(
    posts: list[dict[str, Any]],
    stats_by_video: dict[str, dict[str, int]],
    clicks: list[dict[str, Any]],
    commission: list[dict[str, Any]],
    collected_at: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """게시 기록 + YouTube 통계 + 쿠팡 리포트를 subId로 조인한 스냅샷."""
    clicks_by_sub = _sum_by_sub_id(clicks, "click")
    commission_by_sub = _sum_by_sub_id(commission, "commission")
    orders_by_sub = _sum_by_sub_id(commission, "order")

    videos = []
    attributed_subs: set[str] = set()
    for post in posts:
        vid = post.get("post_id", "")
        sub_id = post.get("sub_id")
        st = stats_by_video.get(vid, {})
        if sub_id:
            attributed_subs.add(sub_id)
        videos.append(
            {
                "video_id": vid,
                "product_id": post.get("product_id"),
                "source": post.get("source", "coupang"),
                "sub_id": sub_id,
                "title": post.get("title"),
                "published_at": post.get("published_at"),
                "views": st.get("views", 0),
                "likes": st.get("likes", 0),
                "comments": st.get("comments", 0),
                # subId 없는 레거시 영상은 귀속 불가(None) — 0과 구분
                "clicks": int(clicks_by_sub.get(sub_id, 0)) if sub_id else None,
                "orders": int(orders_by_sub.get(sub_id, 0)) if sub_id else None,
                "commission": float(commission_by_sub.get(sub_id, 0.0)) if sub_id else None,
            }
        )

    clicks_total = int(sum(clicks_by_sub.values()))
    commission_total = float(sum(commission_by_sub.values()))
    unattributed_clicks = int(
        sum(v for k, v in clicks_by_sub.items() if k not in attributed_subs)
    )
    unattributed_commission = float(
        sum(v for k, v in commission_by_sub.items() if k not in attributed_subs)
    )
    return {
        "collected_at": collected_at,
        "window": {"start": start_date, "end": end_date},
        "videos": videos,
        "channel": {
            "views": sum(v["views"] for v in videos),
            "clicks_total": clicks_total,
            "commission_total": commission_total,
            "unattributed_clicks": unattributed_clicks,
            "unattributed_commission": unattributed_commission,
        },
    }


def summarize(snapshot: dict[str, Any]) -> dict[str, Any]:
    """스냅샷을 사람이 읽는 요약으로: 조회수 내림차순 + 합계."""
    videos = sorted(snapshot["videos"], key=lambda v: v["views"], reverse=True)
    return {
        "window": snapshot["window"],
        "videos": [
            {
                "video_id": v["video_id"],
                "title": v["title"],
                "source": v["source"],
                "views": v["views"],
                "clicks": v["clicks"],
                "orders": v["orders"],
                "commission": v["commission"],
            }
            for v in videos
        ],
        "totals": {
            "views": snapshot["channel"]["views"],
            "clicks": snapshot["channel"]["clicks_total"],
            "commission": snapshot["channel"]["commission_total"],
            "unattributed_clicks": snapshot["channel"]["unattributed_clicks"],
            "unattributed_commission": snapshot["channel"]["unattributed_commission"],
        },
    }


def collect(days: int = 7) -> dict[str, Any]:
    """게시된 영상의 성과를 수집해 metrics.json에 스냅샷 누적, 요약 반환."""
    posts = [
        p
        for p in load_posts()
        if p.get("platform") == "youtube_shorts" and p.get("status") == "PUBLISHED"
    ]
    if not posts:
        return {"status": "EMPTY", "reason": "게시된 영상 없음"}

    stats = fetch_video_stats([p["post_id"] for p in posts if p.get("post_id")])

    end = date.today()
    start = end - timedelta(days=days)
    start_s, end_s = start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
    try:
        clicks = report_clicks(start_s, end_s)
        commission = report_commission(start_s, end_s)
        orders = report_orders(start_s, end_s)
    except Exception as exc:  # noqa: BLE001 — 쿠팡 키 문제로 YouTube 수집까지 버리지 않는다
        clicks, commission, orders = [], [], []
        coupang_error = str(exc)[:200]
    else:
        coupang_error = None

    snapshot = build_snapshot(
        posts,
        stats,
        clicks,
        commission,
        datetime.now(timezone.utc).isoformat(),
        start_s,
        end_s,
    )
    snapshot["coupang_orders"] = orders  # 24시간 쿠키 주문 원본(상품명·gmv 포함)
    if coupang_error:
        snapshot["coupang_error"] = coupang_error

    history = load_metrics()
    history.append(snapshot)
    save_metrics(history)
    return summarize(snapshot)
