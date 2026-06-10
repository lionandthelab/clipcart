"""장면 PNG + TTS → ffmpeg 합성 (1080x1920 30fps Shorts)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from clipcart.video.ff import media_duration, run_ffmpeg
from clipcart.video.frames import compose_scene_frame
from clipcart.video.tts import synthesize

FPS = 30
MIN_SCENE_SECONDS = 2.4
TAIL_PADDING = 0.45


def _zoom_filter(zoom_dir: str, frames: int) -> str:
    # 최대 1.07배: 상하단 크롭 ~3.3%(63px) — 고지 배너(y=152)와 하단 자막을 침범하지 않음
    if zoom_dir == "out":
        z = "max(1.07-0.0005*on,1.0)"
    else:
        z = "min(1.0+0.0005*on,1.07)"
    return (
        "scale=1620:2880:flags=lanczos,"
        f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s=1080x1920:fps={FPS},format=yuv420p"
    )


def render_scene(
    product_img: Image.Image,
    scene: dict[str, Any],
    index: int,
    workdir: Path,
    voice: str,
    rate: str,
) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)
    frame_png = workdir / f"scene_{index}.png"
    audio_mp3 = workdir / f"scene_{index}.mp3"
    out_mp4 = workdir / f"scene_{index}.mp4"

    compose_scene_frame(product_img, scene, frame_png)
    synthesize(scene["narration"], audio_mp3, voice=voice, rate=scene.get("rate") or rate)

    duration = max(media_duration(audio_mp3) + TAIL_PADDING, MIN_SCENE_SECONDS)
    frames = int(duration * FPS)

    run_ffmpeg(
        [
            "-i", str(frame_png),
            "-i", str(audio_mp3),
            "-filter_complex",
            f"[0:v]{_zoom_filter(scene.get('zoom', 'in'), frames)}[v];"
            f"[1:a]aresample=44100,apad=pad_dur=1.0,atrim=0:{duration:.3f}[a]",
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "160k",
            str(out_mp4),
        ]
    )
    return out_mp4


def concat_scenes(scene_files: list[Path], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    inputs: list[str] = []
    for f in scene_files:
        inputs += ["-i", str(f)]
    n = len(scene_files)
    pairs = "".join(f"[{i}:v][{i}:a]" for i in range(n))
    filter_graph = (
        f"{pairs}concat=n={n}:v=1:a=1[v][rawa];"
        "[rawa]loudnorm=I=-16:TP=-1.5:LRA=11[a]"
    )
    run_ffmpeg(
        [
            *inputs,
            "-filter_complex", filter_graph,
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart",
            str(out_path),
        ],
        timeout=900,
    )
    return out_path


def render_video(
    product_img: Image.Image,
    scenes: list[dict[str, Any]],
    workdir: Path,
    out_path: Path,
    voice: str,
    rate: str,
) -> Path:
    scene_files = [
        render_scene(product_img, scene, i, workdir, voice, rate)
        for i, scene in enumerate(scenes)
    ]
    return concat_scenes(scene_files, out_path)
