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
                    "META_ACCESS_TOKEN": ig.access_token,
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
@click.option("--app-id", envvar="META_APP_ID", help="Instagram: Meta App ID / Pinterest: App ID")
@click.option("--app-secret", envvar="META_APP_SECRET", help="Instagram: Meta App Secret")
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
            click.echo("META_APP_ID, META_APP_SECRET 필요 (.env 또는 --app-id/--app-secret)", err=True)
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
