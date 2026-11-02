"""Ambient focus sound: rain, lo-fi or white noise while the focus timer runs.

The files are CC0 loops in desktop/assets/sounds (see its LICENSE.txt). A file is decoded once into
PCM, its two ends are crossfaded so the loop has no seam, and the PCM is fed to an audio sink in a
circle. White noise is made in code and needs neither a file nor a seam.

Everything that touches a sound card is best-effort, as in sound.py: no card, no multimedia plugin or
a decode that fails leaves FlexWeek silent and working. With FLEXWEEK_SILENT set nothing is opened at
all; the player still tracks what it would be doing, so tests can check the behaviour without noise.

The waveform helpers at the top have no Qt in them, so they can be checked without a sound card.
"""

from __future__ import annotations

import math
import os
import random
from array import array
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QIODevice, QObject, QTimer, QUrl, Signal

from desktop.native.sound import SILENT

if TYPE_CHECKING:
    from PySide6.QtMultimedia import QAudioDecoder, QAudioSink

SOUND_DIR = Path(__file__).resolve().parents[1] / "assets" / "sounds"
# What the stored `focus_audio` preference calls each sound that plays inside FlexWeek. "spotify" is
# not here: it opens the student's own app and FlexWeek does not control it.
FILES = {"rain": "soft-rain-loop.mp3", "lo-fi": "lofi-hip-hop-loop.ogg"}
WHITE_NOISE = "white-noise"
SOUNDS = (*FILES, WHITE_NOISE)

RATE = 44_100
CHANNELS = 2
FRAME = CHANNELS * 2
# How much of the end of a loop is blended into its start. Rain hides a long blend; a beat would blur.
SEAM_MS = {"rain": 900, "lo-fi": 400}
NOISE_SECONDS = 6
# Every sound is brought to the same loudness, so rain is not louder than a beat. The sink volume is
# this times the app's alert volume.
TARGET_RMS = 0.05
FADE_MS = 700
FADE_STEP_MS = 35


def white_noise(seconds: float = NOISE_SECONDS, rng: random.Random | None = None) -> bytes:
    """Stereo 16-bit white noise at TARGET_RMS. Uniform samples, so the loop point is inaudible."""
    source = rng or random.Random()
    peak = round(TARGET_RMS * math.sqrt(3) * 32767)
    samples = array("h", (source.randint(-peak, peak) for _ in range(round(seconds * RATE) * CHANNELS)))
    return samples.tobytes()


def rms(pcm: bytes) -> float:
    """Loudness of 16-bit PCM from 0 to 1, read from every 8th sample, which is plenty for a gain."""
    samples = array("h")
    samples.frombytes(pcm[: len(pcm) - len(pcm) % 2])
    if not samples:
        return 0.0
    picked = samples[::8]
    return math.sqrt(sum(value * value for value in picked) / len(picked)) / 32768.0


def loudness_gain(pcm: bytes) -> float:
    """A gain at most 1 that brings a sound down to TARGET_RMS. Quiet sounds are not raised."""
    level = rms(pcm)
    return 1.0 if level <= TARGET_RMS else TARGET_RMS / level


def seam(pcm: bytes, blend_frames: int) -> bytes:
    """Make `pcm` loop without a click: the last `blend_frames` fade out into the first ones.

    The result is that many frames shorter. Its end is the unfaded sound up to where the blended
    start picks up again, so the sample after the last one is the sample that really followed it.
    Equal-power curves keep the loudness steady through the blend.
    """
    frames = len(pcm) // FRAME
    blend = min(blend_frames, frames // 2)
    if blend <= 0:
        return pcm[: frames * FRAME]
    source = array("h")
    source.frombytes(pcm[: frames * FRAME])
    keep = frames - blend
    out = array("h", source[: keep * CHANNELS])
    for index in range(blend):
        angle = (index + 0.5) / blend * math.pi / 2
        fade_in, fade_out = math.sin(angle), math.cos(angle)
        for channel in range(CHANNELS):
            head = source[index * CHANNELS + channel]
            tail = source[(keep + index) * CHANNELS + channel]
            out[index * CHANNELS + channel] = round(head * fade_in + tail * fade_out)
    return out.tobytes()


class LoopDevice(QIODevice):
    """PCM that never ends: reading past the last frame carries on from the first."""

    def __init__(self, pcm: bytes, parent: QObject | None = None) -> None:
        super().__init__(parent)
        if len(pcm) < FRAME:
            raise ValueError("a loop needs at least one frame")
        self._pcm = pcm[: len(pcm) - len(pcm) % FRAME]
        self._at = 0

    def isSequential(self) -> bool:  # noqa: N802
        return True

    def bytesAvailable(self) -> int:  # noqa: N802
        return len(self._pcm) + super().bytesAvailable()

    def readData(self, maxlen: int) -> bytes:  # noqa: N802
        want = maxlen - maxlen % FRAME
        if want <= 0:
            return b""
        out = bytearray()
        while len(out) < want:
            chunk = self._pcm[self._at : self._at + want - len(out)]
            out += chunk
            self._at = (self._at + len(chunk)) % len(self._pcm)
        return bytes(out)

    def writeData(self, _data: Any, _length: int = 0) -> int:  # noqa: N802
        return -1


class AmbientPlayer(QObject):
    """One ambient voice. States: stopped, loading (a file is being decoded), playing, paused."""

    state_changed = Signal(str)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        fade_ms: int = FADE_MS,
        sink_factory: Any = None,
    ) -> None:
        super().__init__(parent)
        self._fade_ms = fade_ms
        self._sink_factory = sink_factory or _open_sink
        self._state = "stopped"
        self._kind = ""
        self._volume = 80.0
        self._cache: dict[str, tuple[bytes, float]] = {}
        self._decoder: QAudioDecoder | None = None
        self._pieces: list[bytes] = []
        self._decoding = ""
        self._sink: QAudioSink | None = None
        self._device: LoopDevice | None = None
        self._gain = 1.0
        self._ramp = 0.0
        self._ramp_to = 0.0
        self._after: str = ""
        self._timer = QTimer(self)
        self._timer.setInterval(FADE_STEP_MS)
        self._timer.timeout.connect(self._step)

    @property
    def state(self) -> str:
        return self._state

    @property
    def kind(self) -> str:
        return self._kind

    @property
    def audible(self) -> bool:
        """True while a sink is open and not paused: what a listener could hear if the volume is up."""
        return self._sink is not None and self._state == "playing"

    def loop_pcm(self, kind: str) -> bytes | None:
        """The seamless loop for `kind` once it is ready, for checks."""
        entry = self._cache.get(kind)
        return None if entry is None else entry[0]

    def play(self, kind: str, volume: float) -> None:
        """Start `kind`, or carry on with it if it is the sound already chosen. Anything else stops."""
        if kind not in SOUNDS:
            self.stop()
            return
        self._volume = volume
        if kind == self._kind and self._state in ("playing", "loading"):
            self._apply_volume()
            return
        if kind == self._kind and self._state == "paused":
            self.resume()
            return
        self._drop_sink()
        self._kind = kind
        self._set_state("loading")
        self._ready(kind)

    def pause(self) -> None:
        if self._state == "loading":
            self._set_state("paused")
            return
        if self._state != "playing":
            return
        self._set_state("paused")
        if self._sink is None:
            return
        self._after = "suspend"
        self._fade(0.0)

    def resume(self) -> None:
        if self._state != "paused":
            return
        if self._sink is None:
            self._set_state("loading")
            self._ready(self._kind)
            return
        self._after = ""
        self._set_state("playing")
        self._sink.resume()
        self._fade(1.0)

    def stop(self) -> None:
        was = self._state
        self._kind = ""
        self._pieces = []
        self._decoding = ""
        if self._decoder is not None:
            self._decoder.stop()
        if was == "stopped":
            return
        self._set_state("stopped")
        if self._sink is None or self._fade_ms <= 0 or was == "paused":
            self._drop_sink()
            return
        self._after = "stop"
        self._fade(0.0)

    def set_volume(self, volume: float) -> None:
        self._volume = volume
        self._apply_volume()

    def finish_fade(self) -> None:
        """Jump to the end of a fade in progress. Tests and shutdown use it."""
        if self._timer.isActive():
            self._ramp = self._ramp_to
            self._step()

    def _set_state(self, state: str) -> None:
        if state != self._state:
            self._state = state
            self.state_changed.emit(state)

    def _ready(self, kind: str) -> None:
        if kind in self._cache:
            self._begin()
        elif kind == WHITE_NOISE:
            pcm = white_noise()
            self._cache[kind] = (pcm, 1.0)
            self._begin()
        else:
            self._decode(kind)

    def _decode(self, kind: str) -> None:
        path = SOUND_DIR / FILES[kind]
        try:
            from PySide6.QtMultimedia import QAudioDecoder, QAudioFormat

            decoder = QAudioDecoder(self)
            shape = QAudioFormat()
            shape.setSampleRate(RATE)
            shape.setChannelCount(CHANNELS)
            shape.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            decoder.setAudioFormat(shape)
            decoder.setSource(QUrl.fromLocalFile(str(path)))
            decoder.bufferReady.connect(self._piece)
            decoder.finished.connect(self._decoded)
            decoder.error.connect(self._decode_failed)
        except Exception:
            self._give_up()
            return
        if self._decoder is not None:
            self._decoder.stop()
            self._decoder.deleteLater()
        self._decoder = decoder
        self._decoding = kind
        self._pieces = []
        decoder.start()

    def _piece(self) -> None:
        decoder = self._decoder
        if decoder is None:
            return
        buffer = decoder.read()
        if buffer.isValid():
            self._pieces.append(bytes(buffer.constData()))

    def _decoded(self) -> None:
        kind = self._decoding
        if not kind:
            return
        self._decoding = ""
        pcm = b"".join(self._pieces)
        self._pieces = []
        if len(pcm) < FRAME * RATE:
            self._give_up()
            return
        gain = loudness_gain(pcm)
        self._cache[kind] = (seam(pcm, SEAM_MS[kind] * RATE // 1000), gain)
        if self._kind == kind and self._state == "loading":
            self._begin()

    def _decode_failed(self, *_args: object) -> None:
        self._give_up()

    def _give_up(self) -> None:
        """A sound that cannot be read leaves the focus timer running in silence."""
        self._decoding = ""
        self._pieces = []
        self._kind = ""
        self._set_state("stopped")

    def _begin(self) -> None:
        entry = self._cache.get(self._kind)
        if entry is None:
            return
        pcm, self._gain = entry
        self._set_state("playing")
        if os.environ.get(SILENT):
            return
        try:
            self._device = LoopDevice(pcm, self)
            self._device.open(QIODevice.OpenModeFlag.ReadOnly)
            self._sink = self._sink_factory(self)
        except Exception:
            self._sink = None
        if self._sink is None:
            self._device = None
            return
        self._ramp = 0.0
        self._apply_volume()
        self._sink.start(self._device)
        self._after = ""
        self._fade(1.0)

    def _level(self) -> float:
        return max(0.0, min(100.0, float(self._volume or 0))) / 100.0 * self._gain

    def _apply_volume(self) -> None:
        if self._sink is not None:
            self._sink.setVolume(self._level() * self._ramp)

    def _fade(self, target: float) -> None:
        self._ramp_to = target
        if self._fade_ms <= 0 or self._sink is None:
            self._ramp = target
            self._arrive()
            return
        self._timer.start()

    def _step(self) -> None:
        distance = FADE_STEP_MS / self._fade_ms
        if self._ramp < self._ramp_to:
            self._ramp = min(self._ramp_to, self._ramp + distance)
        else:
            self._ramp = max(self._ramp_to, self._ramp - distance)
        self._apply_volume()
        if self._ramp == self._ramp_to:
            self._timer.stop()
            self._arrive()

    def _arrive(self) -> None:
        self._apply_volume()
        after, self._after = self._after, ""
        if after == "suspend" and self._sink is not None and self._state == "paused":
            self._sink.suspend()
        elif after == "stop" and self._state == "stopped":
            self._drop_sink()

    def _drop_sink(self) -> None:
        self._timer.stop()
        self._after = ""
        sink, self._sink = self._sink, None
        if sink is not None:
            sink.stop()
            sink.deleteLater()
        if self._device is not None:
            self._device.close()
            self._device = None


def _open_sink(parent: QObject) -> QAudioSink | None:
    from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices

    device = QMediaDevices.defaultAudioOutput()
    if device is None or device.isNull():
        return None
    shape = QAudioFormat()
    shape.setSampleRate(RATE)
    shape.setChannelCount(CHANNELS)
    shape.setSampleFormat(QAudioFormat.SampleFormat.Int16)
    if not device.isFormatSupported(shape):
        return None
    return QAudioSink(device, shape, parent)


class FocusAudio(QObject):
    """Follows the session's focus timer: plays while it works, holds still on a pause or a break, and
    stops when the session ends or is left."""

    def __init__(self, session: Any, parent: QObject | None = None, player: AmbientPlayer | None = None) -> None:
        super().__init__(parent)
        self._session = session
        self.player = player or AmbientPlayer(self)
        session.focus_changed.connect(self.sync)

    def sync(self) -> None:
        prefs = self._session.preferences or {}
        kind = prefs.get("focus_audio") or "off"
        state = self._session.focus
        phase = None if state is None else state.get("phase")
        if kind not in SOUNDS or state is None or phase == "ended":
            self.player.stop()
        elif phase == "work" and state.get("running"):
            self.player.play(kind, prefs.get("alert_volume", 80))
        else:
            self.player.set_volume(prefs.get("alert_volume", 80))
            self.player.pause()
