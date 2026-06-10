"""ffmpeg/ffprobe 경로 탐색 및 실행 헬퍼."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

from clipcart.config import PROJECT_ROOT


@lru_cache(maxsize=1)
def ffmpeg_exe() -> str:
    env = os.getenv("FFMPEG_PATH")
    if env and Path(env).is_file():
        return env
    local = list((PROJECT_ROOT / "tools").glob("**/bin/ffmpeg.exe"))
    if local:
        return str(local[0])
    on_path = shutil.which("ffmpeg")
    if on_path:
        return on_path
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("ffmpeg를 찾을 수 없음 (tools/ffmpeg 또는 PATH)") from exc


@lru_cache(maxsize=1)
def ffprobe_exe() -> str | None:
    env = os.getenv("FFPROBE_PATH")
    if env and Path(env).is_file():
        return env
    local = list((PROJECT_ROOT / "tools").glob("**/bin/ffprobe.exe"))
    if local:
        return str(local[0])
    return shutil.which("ffprobe")


def run_ffmpeg(args: list[str], timeout: int = 600) -> None:
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg 실패: {proc.stderr[-800:]}")


_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)")


def media_duration(path: Path) -> float:
    probe = ffprobe_exe()
    if probe:
        proc = subprocess.run(
            [probe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        try:
            return float(proc.stdout.strip())
        except ValueError:
            pass
    # ffprobe 없으면 ffmpeg -i 의 stderr에서 Duration 파싱
    proc = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    match = _DURATION_RE.search(proc.stderr)
    if not match:
        raise RuntimeError(f"길이 파싱 실패: {path}")
    h, m, s = match.groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def video_resolution(path: Path) -> tuple[int, int]:
    probe = ffprobe_exe()
    if probe:
        proc = subprocess.run(
            [
                probe, "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", str(path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        out = proc.stdout.strip().split("\n")[0]
        if "x" in out:
            w, h = out.split("x")[:2]
            return int(w), int(h)
    proc = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    match = re.search(r"Video:.*?(\d{3,4})x(\d{3,4})", proc.stderr)
    if not match:
        raise RuntimeError(f"해상도 파싱 실패: {path}")
    return int(match.group(1)), int(match.group(2))
