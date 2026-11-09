"""Ambient focus sound: the loop, the volume, pause and stop, silent mode, and following the timer.

Nobody can listen during a test, so what is checked is the data the sink would be fed and what the
player asks the sink to do. Expected values come from the requirements (a loop that wraps, a volume
that follows the app's, a file's real length), not from what the code printed.
"""

from __future__ import annotations

import os
import random
from array import array
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QIODevice, QObject, Signal  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native import ambient  # noqa: E402
from desktop.native.ambient import (  # noqa: E402
    FRAME,
    RATE,
    TARGET_RMS,
    AmbientPlayer,
    FocusAudio,
    LoopDevice,
    loudness_gain,
    rms,
    seam,
    white_noise,
)
from desktop.native.sound import SILENT  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-ambient"])


class FakeSink(QObject):
    """What a QAudioSink is asked to do, written down."""

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self.volume = -1.0
        self.fed: QIODevice | None = None
        self.suspended = False
        self.stopped = False
        self.starts = 0
        self.resumes = 0

    def setVolume(self, value: float) -> None:  # noqa: N802
        self.volume = value

    def start(self, device: QIODevice) -> None:
        self.fed = device
        self.starts += 1

    def suspend(self) -> None:
        self.suspended = True

    def resume(self) -> None:
        self.suspended = False
        self.resumes += 1

    def stop(self) -> None:
        self.stopped = True


def sink_maker(made: list[FakeSink]):
    def make(parent: QObject) -> FakeSink:
        sink = FakeSink(parent)
        made.append(sink)
        return sink

    return make


@pytest.fixture()
def heard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Silent mode off, so the player opens its (fake) sink as it would for a person."""
    monkeypatch.delenv(SILENT, raising=False)


def stereo(values: list[int]) -> bytes:
    return array("h", [value for value in values for _ in range(2)]).tobytes()


def test_white_noise_is_the_asked_length_steady_and_not_a_copy_of_itself() -> None:
    noise = white_noise(2, random.Random(1))
    assert len(noise) == 2 * RATE * FRAME
    assert TARGET_RMS * 0.9 < rms(noise) < TARGET_RMS * 1.1
    assert noise != white_noise(2, random.Random(2))
    assert noise == white_noise(2, random.Random(1))


def test_a_loud_sound_is_brought_down_to_the_target_and_a_quiet_one_is_left_alone() -> None:
    loud = array("h", [20000, -20000] * 4000).tobytes()
    assert rms(loud) * loudness_gain(loud) == pytest.approx(TARGET_RMS, rel=0.02)
    quiet = array("h", [100, -100] * 4000).tobytes()
    assert loudness_gain(quiet) == 1.0


def test_the_seam_turns_a_jump_at_the_loop_point_into_a_smooth_step() -> None:
    length, blend = 4000, 400
    low, high = -20000, 20000
    ramp = [round(low + (high - low) * index / (length - 1)) for index in range(length)]
    original = array("h")
    original.frombytes(stereo(ramp))
    assert abs(original[-2] - original[0]) == high - low  # the wrap of the raw file: a full-scale click

    looped = array("h")
    looped.frombytes(seam(stereo(ramp), blend))
    assert len(looped) // 2 == length - blend
    step = (high - low) / (length - 1)
    # The head and tail here are as unrelated as two sounds can be, so a little of the head leaks into the
    # first frame; the click must still be a small fraction of the original's.
    assert abs(looped[-2] - looped[0]) <= (high - low) / 500
    inside = max(abs(looped[index + 2] - looped[index]) for index in range(0, len(looped) - 2, 2))
    assert inside <= (high - low) / 200
    assert step < (high - low) / 500


def test_the_seam_keeps_steady_loudness_through_the_blend() -> None:
    """Rain is noise: its tail and head are unrelated, so equal-power curves must not dip or swell."""
    looped = seam(white_noise(2, random.Random(3)), RATE // 2)
    blended = rms(looped[: RATE // 2 * FRAME])
    body = rms(looped[RATE // 2 * FRAME :])
    assert blended == pytest.approx(body, rel=0.08)


def test_a_loop_device_wraps_and_only_hands_out_whole_frames() -> None:
    a, b, c = (bytes([value]) * FRAME for value in (1, 2, 3))
    device = LoopDevice(a + b + c)
    # readData is what the sink's reads end in; QIODevice.read may read ahead into its own buffer.
    assert device.readData(5 * FRAME) == a + b + c + a + b
    assert device.readData(FRAME + 3) == c  # three extra bytes are not a frame; none are handed out
    assert device.readData(2) == b""
    with pytest.raises(ValueError):
        LoopDevice(b"\x00\x00")


def test_silent_mode_opens_nothing_but_still_follows_the_timer(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(SILENT, "1")
    made: list[FakeSink] = []
    player = AmbientPlayer(fade_ms=0, sink_factory=sink_maker(made))
    player.play("white-noise", 80)
    assert player.state == "playing" and player.kind == "white-noise"
    assert made == [] and not player.audible
    player.pause()
    assert player.state == "paused"
    player.resume()
    assert player.state == "playing"
    player.stop()
    assert player.state == "stopped" and made == []


def test_playing_feeds_a_looping_sink_at_the_apps_volume(qapp: QApplication, heard: None) -> None:
    made: list[FakeSink] = []
    player = AmbientPlayer(fade_ms=0, sink_factory=sink_maker(made))
    player.play("white-noise", 80)
    assert player.audible and len(made) == 1
    sink = made[0]
    assert sink.starts == 1 and isinstance(sink.fed, LoopDevice)
    assert sink.volume == pytest.approx(0.8)  # white noise is generated at the target loudness: gain 1
    assert len(sink.fed.read(10 * RATE * FRAME)) == 10 * RATE * FRAME  # longer than its buffer: it wraps
    player.set_volume(25)
    assert sink.volume == pytest.approx(0.25)
    player.set_volume(0)
    assert sink.volume == 0.0
    player.play("white-noise", 80)  # the timer ticking again changes nothing and opens no second sink
    assert len(made) == 1 and sink.volume == pytest.approx(0.8)


def test_pause_silences_the_sink_and_resume_brings_it_back(qapp: QApplication, heard: None) -> None:
    made: list[FakeSink] = []
    player = AmbientPlayer(fade_ms=0, sink_factory=sink_maker(made))
    player.play("white-noise", 80)
    sink = made[0]
    player.pause()
    assert player.state == "paused" and not player.audible
    assert sink.suspended and sink.volume == 0.0
    player.resume()
    assert player.state == "playing" and player.audible
    assert not sink.suspended and sink.resumes == 1 and sink.volume == pytest.approx(0.8)
    assert len(made) == 1


def test_stop_closes_the_sink_and_a_new_play_opens_a_fresh_one(qapp: QApplication, heard: None) -> None:
    made: list[FakeSink] = []
    player = AmbientPlayer(fade_ms=0, sink_factory=sink_maker(made))
    player.play("white-noise", 80)
    player.stop()
    assert player.state == "stopped" and made[0].stopped and not player.audible
    player.play("white-noise", 80)
    assert len(made) == 2 and not made[1].stopped


def test_fades_move_the_volume_in_steps_not_in_one_jump(qapp: QApplication, heard: None) -> None:
    made: list[FakeSink] = []
    player = AmbientPlayer(fade_ms=200, sink_factory=sink_maker(made))
    player.play("white-noise", 100)
    sink = made[0]
    assert sink.volume == 0.0  # starts silent
    wait_until(qapp, lambda: sink.volume > 0.0)
    assert sink.volume < 1.0
    wait_until(qapp, lambda: sink.volume == pytest.approx(1.0))
    player.pause()
    wait_until(qapp, lambda: 0.0 < sink.volume < 1.0)
    assert not sink.suspended  # still fading out
    wait_until(qapp, lambda: sink.suspended)
    assert sink.volume == 0.0
    player.resume()
    wait_until(qapp, lambda: sink.volume == pytest.approx(1.0))
    player.stop()
    wait_until(qapp, lambda: sink.stopped)


def test_a_failed_sink_leaves_the_player_running_without_sound(qapp: QApplication, heard: None) -> None:
    player = AmbientPlayer(fade_ms=0, sink_factory=lambda _parent: None)
    player.play("white-noise", 80)
    assert player.state == "playing" and not player.audible
    player.stop()


def test_an_unknown_sound_stops_what_is_playing(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SILENT, "1")
    player = AmbientPlayer(fade_ms=0)
    player.play("white-noise", 80)
    player.play("spotify", 80)
    assert player.state == "stopped"


@pytest.mark.parametrize(
    ("kind", "seconds", "blend"),
    [("rain", 22.5, 0.9), ("lo-fi", 127.9, 0.4)],
)
def test_each_file_decodes_into_a_loop_as_long_as_the_file_less_its_blend(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, kind: str, seconds: float, blend: float
) -> None:
    """The lengths are the files' own, from ffprobe: rain 22.51 s, lo-fi 127.89 s."""
    monkeypatch.setenv(SILENT, "1")
    player = AmbientPlayer(fade_ms=0)
    player.play(kind, 80)
    assert player.state == "loading"
    wait_until(qapp, lambda: player.state == "playing", 20)
    loop = player.loop_pcm(kind)
    assert loop is not None
    assert len(loop) % FRAME == 0
    assert len(loop) / FRAME / RATE == pytest.approx(seconds - blend, abs=0.3)
    entry = player._cache[kind]
    assert rms(loop) * entry[1] <= TARGET_RMS * 1.15
    player.stop()


def test_pausing_while_a_file_is_still_loading_waits_and_resume_starts_it(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(SILENT, "1")
    player = AmbientPlayer(fade_ms=0)
    player.play("rain", 80)
    player.pause()
    assert player.state == "paused"
    wait_until(qapp, lambda: player.loop_pcm("rain") is not None, 20)
    assert player.state == "paused"
    player.resume()
    assert player.state == "playing"
    player.stop()


class FakeSession(QObject):
    focus_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.focus: dict | None = None
        self.preferences: dict = {"focus_audio": "white-noise", "alert_volume": 80}


def timer(phase: str, running: bool = True) -> dict:
    return {"phase": phase, "running": running, "title": "History essay"}


def test_the_sound_follows_the_timer_through_every_phase(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(SILENT, "1")
    session = FakeSession()
    follower = FocusAudio(session, player=AmbientPlayer(fade_ms=0))
    player = follower.player

    def settle(focus: dict | None) -> str:
        session.focus = focus
        session.focus_changed.emit()
        return player.state

    assert settle(None) == "stopped"
    assert settle(timer("work")) == "playing"
    assert settle(timer("work", running=False)) == "paused"  # Pause
    assert settle(timer("work")) == "playing"  # Resume
    assert settle(timer("break")) == "paused"  # a break
    assert settle(timer("long_break")) == "paused"
    assert settle(timer("work")) == "playing"  # back to work
    assert settle(timer("ended", running=False)) == "stopped"  # the session finished
    assert settle(timer("work")) == "playing"
    assert settle(None) == "stopped"  # Finish or Back reset the timer


@pytest.mark.parametrize("choice", ["off", "spotify", None])
def test_only_the_three_ambient_choices_ever_play(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, choice: str | None
) -> None:
    monkeypatch.setenv(SILENT, "1")
    session = FakeSession()
    session.preferences = {"alert_volume": 80} if choice is None else {"focus_audio": choice}
    follower = FocusAudio(session, player=AmbientPlayer(fade_ms=0))
    session.focus = timer("work")
    session.focus_changed.emit()
    assert follower.player.state == "stopped"


def test_changing_the_choice_mid_session_swaps_the_sound(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(SILENT, "1")
    session = FakeSession()
    follower = FocusAudio(session, player=AmbientPlayer(fade_ms=0))
    session.focus = timer("work")
    session.focus_changed.emit()
    assert follower.player.kind == "white-noise"
    session.preferences = {"focus_audio": "off"}
    session.focus_changed.emit()
    assert follower.player.state == "stopped"


def test_the_sound_files_and_their_licence_note_are_in_the_assets() -> None:
    folder = Path(ambient.SOUND_DIR)
    for name in ambient.FILES.values():
        assert (folder / name).is_file()
    note = (folder / "LICENSE.txt").read_text(encoding="utf-8")
    for needed in (
        "Soft Rain Loop",
        "_lynks",
        "https://freesound.org/people/_lynks/sounds/595717/",
        "Lofi Hip Hop Loop",
        "omfgdude",
        "https://opengameart.org/content/lofi-hip-hop-loop",
        "CC0 1.0",
    ):
        assert needed in note
