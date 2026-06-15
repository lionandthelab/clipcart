"""IG Reels용 공개 영상 호스팅 — S3 호환 스토리지(Cloudflare R2/S3/B2)에 업로드.

Instagram Content Publishing API 는 파일 업로드가 아니라 **공개 video_url** 로 영상을
가져간다. GitHub Pages 는 안정적이나 git 히스토리가 비대해지고, Release 에셋은
content-type=octet-stream + 만료 서명 URL 이라 IG 가 거부할 수 있다. 그래서 영상
파이프라인 정석인 오브젝트 스토리지에 `video/mp4` 로 올려 직접 URL 을 만든다.

env 미설정이면 None(soft-fail) → 호출부가 수동 video_url 안내. R2 권장(무료·egress 무료).
"""

from __future__ import annotations

import os
from pathlib import Path

_ENV = (
    "CLIPCART_S3_ENDPOINT",     # 예: https://<account>.r2.cloudflarestorage.com
    "CLIPCART_S3_BUCKET",
    "CLIPCART_S3_ACCESS_KEY",
    "CLIPCART_S3_SECRET_KEY",
    "CLIPCART_S3_PUBLIC_BASE",  # 공개 베이스 URL 예: https://<bucket>.<id>.r2.dev (또는 커스텀 도메인)
)


def configured() -> bool:
    return all((os.getenv(k) or "").strip() for k in _ENV)


def _client():
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=(os.getenv("CLIPCART_S3_ENDPOINT") or "").strip(),
        aws_access_key_id=(os.getenv("CLIPCART_S3_ACCESS_KEY") or "").strip(),
        aws_secret_access_key=(os.getenv("CLIPCART_S3_SECRET_KEY") or "").strip(),
        config=Config(signature_version="s3v4"),
    )


def host_video(path: str | Path, key_prefix: str = "reels") -> str | None:
    """MP4 를 공개 직접 URL(video/mp4)로 업로드 후 URL 반환. 실패/미설정 시 None."""
    if not configured():
        return None
    p = Path(path)
    if not p.exists():
        return None
    bucket = (os.getenv("CLIPCART_S3_BUCKET") or "").strip()
    base = (os.getenv("CLIPCART_S3_PUBLIC_BASE") or "").strip().rstrip("/")
    key = f"{key_prefix.strip('/')}/{p.name}"
    try:
        _client().upload_file(str(p), bucket, key, ExtraArgs={"ContentType": "video/mp4"})
        return f"{base}/{key}"
    except ImportError:
        print("  [media_host] boto3 미설치 — `pip install boto3`")
        return None
    except Exception as e:  # noqa: BLE001
        print(f"  [media_host] 업로드 실패: {str(e)[:180]}")
        return None
