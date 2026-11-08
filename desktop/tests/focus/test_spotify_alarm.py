"""A Spotify alarm plays in the student's own Spotify app, is never silent while it starts, and names
the song once it is heard. Every test talks to a pretend Spotify: none may reach a real one."""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtWidgets import QApplication

    from desktop.native.settings import AlarmRingDialog
    from desktop.native.window import NativeWindow
    from desktop.tests.focus.support_spotify import TRACK, PretendSpotify, player
    from desktop.tests.waiting import wait_until


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-spotify-alarm-test"])


class Bells:
    def __init__(self) -> None:
        self.rung: list[str] = []
        self.stopped = 0

    def start(self, tone: str, _volume: float) -> bool:
        self.rung.append(tone)
        return True

    def once(self, tone: str, _volume: float) -> bool:
        self.rung.append(tone)
        return True

    def stop(self) -> None:
        self.stopped += 1


def alarm_window(app: Any) -> Any:
    """Just what ringing an alarm uses of the window: its bell, its Spotify, its ringing dialog."""
    window = SimpleNamespace(
        _bell=Bells(),
        _spotify=player(app),
        session=SimpleNamespace(preferences={"alert_volume": 60}, spotify_url=lambda value=None: value or ""),
        _alarm_dialog=AlarmRingDialog(None, {"name": "Wake up", "time": "07:00"}, TRACK),
    )
    window._spotify.late.connect(lambda: NativeWindow._spotify_late(window))
    window._spotify.heard.connect(lambda words: NativeWindow._spotify_heard(window, words))
    return window


def test_an_alarm_plays_in_spotify_names_the_song_and_rings_no_tone_once_heard(qapp: QApplication) -> None:
    app = PretendSpotify()
    window = alarm_window(app)
    NativeWindow._ring(window, {"name": "Wake up", "sound": "spotify"}, TRACK)
    assert window._bell.rung == []
    wait_until(
        qapp,
        lambda: window._alarm_dialog.playing.text() != "",
        what="the dialog never named the song",
    )
    assert window._alarm_dialog.playing.text() == "Playing “Voices of the Chord” by Sawano Hiroyuki, mpi"
    assert window._bell.rung == []


def test_an_alarm_whose_song_does_not_start_rings_the_tone_until_it_does(qapp: QApplication) -> None:
    app = PretendSpotify(plays=False)
    window = alarm_window(app)
    NativeWindow._ring(window, {"name": "Wake up", "sound": "spotify"}, TRACK)
    wait_until(qapp, lambda: window._bell.rung == ["chime"], what=lambda: f"rang {window._bell.rung}")
    app.plays = True
    wait_until(qapp, lambda: window._bell.stopped >= 1, what="the music never took over from the tone")
    wait_until(qapp, lambda: window._alarm_dialog.playing.text().startswith("Playing"))
