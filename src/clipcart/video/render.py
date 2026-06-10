"""장면별 프레임 합성(줌+카라오케 자막) + TTS/효과음 믹스 → ffmpeg 인코딩."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from clipcart.video import sfx
from clipcart.video.ff import media_duration, run_ffmpeg
from clipcart.video.frames import (
    draw_chrome,
    draw_cta_static,
    draw_product_card_static,
    make_photo_base,
    zoom_crop,
)
from clipcart.video.kinetic import Caption
from clipcart.video.tts import synthesize_marks

FPS = 30
MIN_SCENE_SECONDS = 1.7
HEAD_PADDING = 0.0
TAIL_PADDING = 0.22


def _zoom_factor(zoom_dir: str, t: float, duration: float) -> float:
    p = min(max(t / duration, 0.0), 1.0)
    # 펀치-인: 빠르게 들어와 안정(ease-out). 최대 1.10배(상하단 안전).
    if zoom_dir == "out":
        return 1.02 + 0.08 * (p ** 0.6)
    return 1.10 - 0.08 * (p ** 0.5)


def _cap_config(scene: dict[str, Any]) -> dict[str, Any]:
    name = scene["name"]
    if name == "hook":
        return {"font_size": 94, "max_words": 4, "bottom": 1180, "highlight": "#FFD400"}
    if name == "downside_cta":
        return {"font_size": 68, "max_words": 5, "bottom": 1300, "highlight": "#FF5A4D"}
    if name == "product":
        return {"font_size": 64, "max_words": 5, "bottom": 1680}
    return {"font_size": 72, "max_words": 5, "bottom": 1660}


def render_scene(
    product_img: Image.Image,
    scene: dict[str, Any],
    index: int,
    workdir: Path,
    voice: str,
    rate: str,
) -> Path:
    framedir = workdir / f"s{index}"
    framedir.mkdir(parents=True, exist_ok=True)
    audio_mp3 = workdir / f"scene_{index}.mp3"
    out_mp4 = workdir / f"scene_{index}.mp4"

    words = synthesize_marks(
        scene["narration"], audio_mp3, voice=voice, rate=scene.get("rate") or rate, pitch=scene.get("pitch", "+0Hz")
    )
    audio_dur = media_duration(audio_mp3)
    duration = max(audio_dur + TAIL_PADDING, MIN_SCENE_SECONDS)

    style = scene.get("style", "zoom_focus")
    base = make_photo_base(product_img, style)
    if style == "white_card":
        draw_product_card_static(
            base,
            scene.get("caption", ""),
            scene.get("price_text", ""),
            scene.get("rocket", False),
            scene.get("sub", ""),
        )

    cap = Caption(words, duration, **_cap_config(scene))
    zoom_dir = scene.get("zoom", "in")
    static_zoom = style == "white_card"

    total_frames = int(duration * FPS)
    for f in range(total_frames):
        t = f / FPS
        if static_zoom:
            frame = base.copy()
        else:
            frame = zoom_crop(base, _zoom_factor(zoom_dir, t, duration))
        if scene["name"] == "downside_cta":
            draw_cta_static(frame, "구매 링크는 설명란에 ▼", scene.get("disclosure", ""))
        draw_chrome(frame)
        cap.draw(frame, t)
        frame.save(framedir / f"{f:05d}.png")

    _encode_scene(framedir, audio_mp3, scene, duration, out_mp4)
    return out_mp4


def _encode_scene(framedir: Path, audio_mp3: Path, scene: dict[str, Any], duration: float, out_mp4: Path) -> None:
    name = scene["name"]
    transition = sfx.riser() if name == "hook" else sfx.whoosh()
    accent = sfx.thud() if name == "downside_cta" else sfx.pop()
    accent_delay = int((HEAD_PADDING + 0.05) * 1000)

    filter_complex = (
        "[1:a]aresample=44100,apad[n];"
        "[2:a]aresample=44100,apad,volume=0.55[w];"
        f"[3:a]aresample=44100,adelay={accent_delay}|{accent_delay},apad,volume=0.5[p];"
        "[n][w][p]amix=inputs=3:duration=longest:normalize=0[a]"
    )
    run_ffmpeg(
        [
            "-framerate", str(FPS), "-i", str(framedir / "%05d.png"),
            "-i", str(audio_mp3),
            "-i", str(transition),
            "-i", str(accent),
            "-filter_complex", filter_complex,
            "-map", "0:v", "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "160k",
            "-t", f"{duration:.3f}",
            str(out_mp4),
        ],
        timeout=600,
    )


def concat_scenes(scene_files: list[Path], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    inputs: list[str] = []
    for f in scene_files:
        inputs += ["-i", str(f)]
    n = len(scene_files)
    pairs = "".join(f"[{i}:v][{i}:a]" for i in range(n))
    filter_graph = (
        f"{pairs}concat=n={n}:v=1:a=1[v][rawa];"
        "[rawa]loudnorm=I=-14:TP=-1.5:LRA=11[a]"
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
