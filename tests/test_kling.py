"""OpenRouter 경유 Kling I2V 클라이언트 단위 테스트 (네트워크 없음)."""

from __future__ import annotations

import clipcart.video.promo.kling as kling


def test_payload_shape_first_frame_audio_off():
    p = kling._payload("data:image/png;base64,AAA", "subtle camera push", 5)
    assert p["model"].startswith("kwaivgi/kling")
    assert p["aspect_ratio"] == "9:16"
    assert p["generate_audio"] is False  # 내레이션과 충돌 방지 — 항상 무음
    fi = p["frame_images"][0]
    assert fi["frame_type"] == "first_frame"
    assert fi["image_url"]["url"].startswith("data:image/png;base64,")


def test_parse_status_completed_with_unsigned_urls():
    state, url = kling._parse_status(
        {"status": "completed", "unsigned_urls": ["https://openrouter.ai/api/v1/files/abc.mp4"]}
    )
    assert state == "success"
    assert url.endswith(".mp4")


def test_parse_status_completed_dict_urls_and_fallbacks():
    state, url = kling._parse_status(
        {"status": "completed", "urls": [{"url": "https://cdn/x.mp4"}]}
    )
    assert (state, url) == ("success", "https://cdn/x.mp4")
    state, url = kling._parse_status({"status": "completed", "video_url": "https://cdn/y.mp4"})
    assert (state, url) == ("success", "https://cdn/y.mp4")


def test_parse_status_completed_without_url_is_failed():
    assert kling._parse_status({"status": "completed"}) == ("failed", None)


def test_parse_status_processing_and_failed():
    assert kling._parse_status({"status": "in_progress"}) == ("processing", None)
    assert kling._parse_status({"status": "failed"}) == ("failed", None)


def test_submit_accepts_202_async():
    # OpenRouter 영상 제출은 202(Accepted)로 응답한다 — 200만 허용하면 안 됨
    assert kling._accepted(202) is True
    assert kling._accepted(200) is True
    assert kling._accepted(402) is False
    assert kling._accepted(400) is False


def test_enabled_respects_env_off(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("CLIPCART_KLING", "off")
    assert kling.enabled() is False
    monkeypatch.setenv("CLIPCART_KLING", "on")
    assert kling.enabled() is True


def test_disabled_without_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("CLIPCART_KLING", "on")
    assert kling.enabled() is False
