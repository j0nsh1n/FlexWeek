"""A recorded play's video: encoded on the GPU, or frames only, never a CPU encode."""

from __future__ import annotations

from pathlib import Path

from scripts.rig import clip


def test_the_video_is_encoded_with_va_api_at_ten_frames_a_second():
    command = clip.encode_command(Path("out/frames"), Path("out/clip.mp4"), Path("/dev/dri/renderD129"))
    assert command[command.index("-c:v") + 1] == "h264_vaapi"
    assert command[command.index("-vaapi_device") + 1] == "/dev/dri/renderD129"
    assert command[command.index("-framerate") + 1] == "10"
    assert command[command.index("-i") + 1] == "out/frames/%05d.jpg"
    assert "hwupload" in command[command.index("-vf") + 1]
    assert "libx264" not in command
    assert command[-1] == "out/clip.mp4"


def test_without_ffmpeg_only_the_frames_are_kept(monkeypatch, tmp_path):
    monkeypatch.setattr(clip.shutil, "which", lambda _name: None)
    note = clip.encode(tmp_path / "frames", tmp_path / "clip.mp4")
    assert note == "No ffmpeg here: frames only."
    assert not (tmp_path / "clip.mp4").exists()


def test_without_a_va_api_device_only_the_frames_are_kept(monkeypatch, tmp_path):
    monkeypatch.setattr(clip.shutil, "which", lambda _name: "/usr/bin/ffmpeg")
    monkeypatch.setattr(clip, "RENDER_NODE", tmp_path / "no-such-device")
    note = clip.encode(tmp_path / "frames", tmp_path / "clip.mp4")
    assert note.startswith("No VA-API device at ")
    assert note.endswith(": frames only.")
