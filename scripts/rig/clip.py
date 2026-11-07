"""Record a play as a clip: frames of the window with the pointer drawn in, and a video when this
computer can encode one on the GPU.

A play with `"record": true` in its setup is recorded (fwtest pictures clips sets it). The frames are
JPEGs in `<out>/frames/`, ten a second. The video is H.264 from VA-API (`h264_vaapi`); with no ffmpeg
(CI installs none) or no VA-API device, only the frames are kept, never a slow CPU encode. What was
made is written to `<out>/clip.json`, which `fwtest pictures clips` reads.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

FRAME_MS = 100
RENDER_NODE = Path("/dev/dri/renderD128")


def encode_command(frames: Path, video: Path, device: Path = RENDER_NODE) -> list[str]:
    """ffmpeg on the GPU: frames at ten a second, even sides (H.264 needs them), uploaded to VA-API."""
    return [
        "ffmpeg",
        "-loglevel",
        "error",
        "-y",
        "-vaapi_device",
        str(device),
        "-framerate",
        str(1000 // FRAME_MS),
        "-i",
        str(frames / "%05d.jpg"),
        "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=nv12,hwupload",
        "-c:v",
        "h264_vaapi",
        str(video),
    ]


def encode(frames: Path, video: Path) -> str:
    """Make the video, or say why there is none. Empty when it was made."""
    if shutil.which("ffmpeg") is None:
        return "No ffmpeg here: frames only."
    if not RENDER_NODE.exists():
        return f"No VA-API device at {RENDER_NODE}: frames only."
    try:
        done = subprocess.run(encode_command(frames, video), capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.SubprocessError) as broken:
        return f"ffmpeg could not run: {broken}"
    if done.returncode != 0 or not video.is_file():
        return "The GPU encode failed: " + (done.stderr.strip().splitlines() or ["no message"])[-1]
    return ""


class Recorder:
    """Frames of `window` every FRAME_MS while it runs, the pointer drawn as a red dot."""

    def __init__(self, window, out: Path) -> None:  # noqa: ANN001 - the app's window, imported late
        from PySide6.QtCore import QTimer

        self.window, self.out = window, out
        self.frames = out / "frames"
        self.count = 0
        self.timer = QTimer()
        self.timer.setInterval(FRAME_MS)
        self.timer.timeout.connect(self.frame)

    def start(self) -> None:
        self.frames.mkdir(parents=True, exist_ok=True)
        self.timer.start()
        self.frame()

    def frame(self) -> None:
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QCursor, QPainter, QPen

        image = self.window.grab().toImage()
        at = self.window.mapFromGlobal(QCursor.pos())
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#ffffff"), 3))
        painter.setBrush(QColor("#e11d48"))
        painter.drawEllipse(QPointF(at), 7, 7)
        painter.end()
        image.save(str(self.frames / f"{self.count:05d}.jpg"), "JPG", 82)
        self.count += 1

    def finish(self) -> dict:
        """Stop, encode, and write clip.json. Returns what it wrote."""
        self.timer.stop()
        names = [f"frames/{number:05d}.jpg" for number in range(self.count)]
        video = self.out / "clip.mp4"
        note = encode(self.frames, video) if self.count else "No frames were recorded."
        made = {"frames": names, "video": None if note else video.name, "note": note}
        (self.out / "clip.json").write_text(json.dumps(made, indent=1) + "\n")
        return made
