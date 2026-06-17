from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import click

from clipcart.config import (
    load_instagram_config,
    load_pinterest_config,
    load_tiktok_config,
)
from clipcart.platforms.verify import verify_all
from clipcart.publishing.publisher import publish_product
from clipcart.research.researcher import find_products
from clipcart.storage import load_products, upsert_product


def _print_json(data: object) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")


def _write_env_vars(values: dict[str, str], env_path: Path) -> None:
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    skip_keys = {k for k in values if k.startswith("_") or k.endswith("_name") or k == "instagram_page" or k == "pinterest_board_name"}
    for key, val in values.items():
        if key in skip_keys:
            continue
        found = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={val}"
                found = True
                break
        if not found:
            lines.append(f"{key}={val}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@click.group()
def main() -> None:
    """살림해결소 clipcart — affiliate 숏폼 자동화 CLI."""


@main.command("find-products")
@click.option("--category", default="청소", help="탐색 카테고리")
@click.option("--max", "max_products", default=30, help="최대 후보 수")
@click.option("--price-min", default=3000, help="최소 가격")
@click.option("--price-max", default=30000, help="최대 가격")
def cmd_find_products(category: str, max_products: int, price_min: int, price_max: int) -> None:
    """FIND PRODUCTS — 상품 탐색 및 점수화."""
    result = find_products(
        category=category,
        price_min=price_min,
        price_max=price_max,
        max_products=max_products,
    )
    _print_json(result)


@main.command("approve")
@click.argument("product_ids")
def cmd_approve(product_ids: str) -> None:
    """APPROVE P001,P002 — 상품 승인."""
    ids = [p.strip() for p in product_ids.replace(" ", "").split(",") if p.strip()]
    approved = []
    for pid in ids:
        products = load_products()
        product = next((p for p in products if p.get("product_id") == pid), None)
        if not product:
            click.echo(f"경고: {pid} 없음", err=True)
            continue
        upsert_product(
            {
                **product,
                "human_approval": "APPROVED",
                "status": "APPROVED_BY_HUMAN",
            }
        )
        approved.append(pid)
    _print_json({"approved": approved, "human_next_step": f"PREPARE TOPVIEW {','.join(approved)}"})


@main.command("reject")
@click.argument("product_ids")
def cmd_reject(product_ids: str) -> None:
    """REJECT P001 — 상품 거절."""
    ids = [p.strip() for p in product_ids.replace(" ", "").split(",") if p.strip()]
    for pid in ids:
        products = load_products()
        product = next((p for p in products if p.get("product_id") == pid), None)
        if product:
            upsert_product({**product, "human_approval": "REJECTED", "status": "REJECTED"})
    _print_json({"rejected": ids})


@main.command("publish")
@click.argument("product_id")
@click.option("--dry-run/--live", default=True, help="dry-run이 기본 (사람 승인 후 --live)")
@click.option(
    "--platform",
    multiple=True,
    help="instagram_reels, tiktok, pinterest",
)
@click.option("--video-url", default=None, help="Instagram Reels용 공개 video URL")
@click.option("--video-path", default=None, type=click.Path(exists=True), help="업로드할 mp4 경로")
@click.option("--cover-url", default=None, help="Pinterest 비디오 Pin 커버 이미지 URL")
def cmd_publish(
    product_id: str,
    dry_run: bool,
    platform: tuple[str, ...],
    video_url: str | None,
    video_path: str | None,
    cover_url: str | None,
) -> None:
    """PUBLISH P001 — 플랫폼 게시 (기본 dry-run)."""
    result = publish_product(
        product_id,
        dry_run=dry_run,
        platforms=list(platform) if platform else None,
        video_url=video_url,
        cover_url=cover_url,
        video_path=Path(video_path) if video_path else None,
    )
    _print_json(result)
    if result.get("status") == "BLOCKED":
        sys.exit(1)


@main.command("daily")
@click.option("--live/--dry-run", default=False, help="--live면 YouTube에 실제 게시")
@click.option("--force", is_flag=True, help="오늘 이미 게시했어도 다시 실행")
@click.option("--keyword", default=None, help="특정 니치 키워드 강제 선택")
@click.option(
    "--source",
    type=click.Choice(["coupang", "aliexpress"]),
    default="coupang",
    help="상품 소스 (기본 coupang, 알리는 aliexpress)",
)
def cmd_daily(live: bool, force: bool, keyword: str | None, source: str) -> None:
    """전자동 데일리 파이프라인: 선정→제작→검수→업로드."""
    from clipcart.pipeline.daily import run_daily

    result = run_daily(live=live, force=force, keyword=keyword, source=source)
    _print_json(result)
    if result.get("status") in {"FAILED", "BLOCKED"}:
        sys.exit(1)


@main.command("metrics")
@click.option("--days", default=7, help="쿠팡 리포트 조회 기간(일)")
def cmd_metrics(days: int) -> None:
    """영상별 성과 수집(YouTube 통계 + 쿠팡 리포트) → metrics.json 누적 + 요약 출력."""
    from clipcart.analytics.collector import collect

    _print_json(collect(days=days))


@main.command("bio")
def cmd_bio() -> None:
    """링크인바이오 정적 페이지 생성 (docs/bio/index.html, 쿠팡은 bio subId 링크)."""
    from clipcart.bio.page import build_bio_page

    _print_json(build_bio_page())


@main.command("analyze")
@click.option("--json", "as_json", is_flag=True, help="구조화 JSON 출력")
@click.option("--collect", is_flag=True, help="분석 전에 metrics 최신 수집")
def cmd_analyze(as_json: bool, collect: bool) -> None:
    """최신 성과 스냅샷을 소스·훅·카테고리별로 집계해 표시."""
    from clipcart.analytics.report import build_report, render_text
    from clipcart.research.history import load_history
    from clipcart.storage import load_metrics

    if collect:
        from clipcart.analytics.collector import collect as run_collect

        run_collect(days=10)

    snaps = load_metrics()
    if not snaps:
        _print_json({"status": "EMPTY", "reason": "metrics.json 비어있음 — clipcart metrics 먼저 실행"})
        return
    report = build_report(snaps[-1], load_history())
    if as_json:
        _print_json(report)
    else:
        click.echo(render_text(report))


@main.command("history")
@click.option("--limit", default=30, help="최근 N건 표시")
def cmd_history(limit: int) -> None:
    """업로드 히스토리(중복 방지 원장) 조회."""
    from clipcart.research.history import load_history

    items = load_history()
    rows = items[-limit:]
    _print_json(
        {
            "total_uploads": len(items),
            "unique_products": len(
                {i.get("coupang_product_id") for i in items if i.get("coupang_product_id")}
                | {i.get("aliexpress_product_id") for i in items if i.get("aliexpress_product_id")}
            ),
            "unique_keywords": len({i.get("niche_keyword") for i in items if i.get("niche_keyword")}),
            "recent": [
                {
                    "date": i.get("date"),
                    "source": i.get("source", "coupang"),
                    "product_name": i.get("product_name"),
                    "niche_keyword": i.get("niche_keyword"),
                    "title": i.get("title"),
                    "post_url": i.get("post_url"),
                }
                for i in rows
            ],
        }
    )


@main.command("status")
def cmd_status() -> None:
    """플랫폼 .env 설정 상태."""
    ig = load_instagram_config()
    tt = load_tiktok_config()
    pin = load_pinterest_config()
    _print_json(
        {
            "instagram_reels": {
                "configured": ig.configured,
                "missing": [k for k, v in {
                    "INSTAGRAM_ACCESS_TOKEN": ig.access_token,
                    "INSTAGRAM_BUSINESS_ACCOUNT_ID": ig.business_account_id,
                }.items() if not v],
                "setup": "clipcart auth instagram",
            },
            "tiktok": {
                "configured": tt.configured,
                "missing": [k for k, v in {
                    "TIKTOK_CLIENT_KEY": tt.client_key,
                    "TIKTOK_CLIENT_SECRET": tt.client_secret,
                    "TIKTOK_ACCESS_TOKEN": tt.access_token,
                }.items() if not v],
                "setup": "clipcart auth tiktok",
            },
            "pinterest": {
                "configured": pin.configured,
                "missing": [k for k, v in {
                    "PINTEREST_APP_ID": pin.app_id,
                    "PINTEREST_APP_SECRET": pin.app_secret,
                    "PINTEREST_ACCESS_TOKEN": pin.access_token,
                    "PINTEREST_BOARD_ID": pin.board_id,
                    "PINTEREST_COVER_IMAGE_URL": pin.default_cover_url,
                }.items() if not v],
                "setup": "clipcart auth pinterest",
            },
            "checked_at": datetime.now().isoformat(),
        }
    )


@main.command("verify")
def cmd_verify() -> None:
    """플랫폼 API 토큰 유효성 검사 (실제 API 호출)."""
    _print_json(verify_all())


@main.command("auth")
@click.argument(
    "platform",
    type=click.Choice(["instagram", "tiktok", "pinterest", "youtube"]),
)
@click.option("--credentials", default=None, help="YouTube: root의 JSON (SA 또는 client_secret)")
@click.option("--app-id", envvar="INSTAGRAM_APP_ID", help="Instagram App ID (Instagram 로그인용, Meta App ID 아님)")
@click.option("--app-secret", envvar="INSTAGRAM_APP_SECRET", help="Instagram App Secret")
@click.option("--client-key", envvar="TIKTOK_CLIENT_KEY")
@click.option("--client-secret", envvar="TIKTOK_CLIENT_SECRET")
@click.option("--pinterest-app-id", envvar="PINTEREST_APP_ID")
@click.option("--pinterest-app-secret", envvar="PINTEREST_APP_SECRET")
@click.option("--youtube-client-id", envvar="YOUTUBE_CLIENT_ID")
@click.option("--youtube-client-secret", envvar="YOUTUBE_CLIENT_SECRET")
@click.option("--save/--no-save", default=True, help=".env에 자동 저장")
def cmd_auth(
    platform: str,
    credentials: str | None,
    app_id: str | None,
    app_secret: str | None,
    client_key: str | None,
    client_secret: str | None,
    pinterest_app_id: str | None,
    pinterest_app_secret: str | None,
    youtube_client_id: str | None,
    youtube_client_secret: str | None,
    save: bool,
) -> None:
    """OAuth 토큰 발급 (Instagram / TikTok / Pinterest / YouTube)."""
    env_path = Path(".env")
    extra: dict[str, str] = {}

    if platform == "instagram":
        if not app_id or not app_secret:
            click.echo(
                "INSTAGRAM_APP_ID, INSTAGRAM_APP_SECRET 필요 (.env 또는 --app-id/--app-secret)\n"
                "  → App Dashboard > Instagram > API setup with Instagram business login\n"
                "    > 3. Set up Instagram business login > Business login settings",
                err=True,
            )
            sys.exit(1)
        from clipcart.auth.meta import setup_instagram_oauth

        extra = setup_instagram_oauth(app_id, app_secret)
        click.echo(f"Instagram 연결: @{extra.get('instagram_page', '')} (IG ID {extra['INSTAGRAM_BUSINESS_ACCOUNT_ID']})")

    elif platform == "tiktok":
        if not client_key or not client_secret:
            click.echo("TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET 필요", err=True)
            sys.exit(1)
        from clipcart.auth.tiktok_auth import setup_tiktok_oauth

        extra = setup_tiktok_oauth(client_key, client_secret)
        click.echo("TikTok OAuth 완료 (video.publish scope 확인)")

    elif platform == "pinterest":
        if not pinterest_app_id or not pinterest_app_secret:
            click.echo("PINTEREST_APP_ID, PINTEREST_APP_SECRET 필요", err=True)
            sys.exit(1)
        from clipcart.auth.pinterest_auth import setup_pinterest_oauth

        extra = setup_pinterest_oauth(pinterest_app_id, pinterest_app_secret)
        board = extra.get("pinterest_board_name", "")
        click.echo(f"Pinterest 연결: board={board} ({extra.get('PINTEREST_BOARD_ID', '')})")

    elif platform == "youtube":
        from clipcart.auth.youtube_auth import setup_youtube

        extra = setup_youtube(
            credentials_path=credentials,
            client_id=youtube_client_id,
            client_secret=youtube_client_secret,
        )
        if extra.get("type") == "service_account":
            click.echo(f"서비스 계정 확인: {extra.get('client_email')} (project: {extra.get('project_id')})")
            click.echo(extra.get("note", ""))
            if extra.get("youtube_ok") == "false":
                click.echo(f"YouTube API 테스트: {extra.get('error', '')[:200]}")
        if extra.get("oauth_required") == "true":
            click.echo(extra.get("oauth_error", ""), err=True)
            sys.exit(1)
        ch = extra.get("youtube_channel_title")
        if ch:
            click.echo(f"YouTube 채널 연결: {ch} ({extra.get('youtube_channel_id', '')})")

    _print_json({k: v for k, v in extra.items() if not k.endswith("_name") and k != "instagram_page"})
    if save:
        _write_env_vars(extra, env_path)
        click.echo(f".env 저장 완료: {env_path.resolve()}")


if __name__ == "__main__":
    main()
