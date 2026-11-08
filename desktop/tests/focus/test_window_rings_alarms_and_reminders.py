# ruff: noqa: F811
"""What the window rings, and with which sound, for an alarm, a reminder and the end of a focus session. A
recorder stands in for the Bell, so the decision is visible without a sound card."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtGui import QDesktopServices  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    SPOTIFY_TRACK,
    RingRecorder,
    no_spotify,
    qapp,  # noqa: F401
    window,  # noqa: F401
)


def _rung(window: NativeWindow, monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    heard: list[tuple[str, str]] = []
    monkeypatch.setattr(window._bell, "once", lambda tone, _volume: heard.append(("once", tone)) or True)
    monkeypatch.setattr(window._bell, "start", lambda tone, _volume: heard.append(("start", tone)) or True)
    return heard


def test_an_alarm_rings_with_the_sound_it_was_given(qapp: QApplication, window: NativeWindow) -> None:
    window._bell = RingRecorder()
    window.session.preferences = {**(window.session.preferences or {}), "alert_volume": 45}
    window._ring({"name": "Practice", "sound": "glass"}, "")
    assert window._bell.started == [("glass", 45)]


def test_an_alarm_set_to_spotify_plays_the_track_instead_of_a_tone(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list = []
    no_spotify(monkeypatch, opened)
    window._bell = RingRecorder()
    window._ring({"name": "Wake up", "sound": "spotify"}, SPOTIFY_TRACK)
    # In the Spotify app, by its own address. A track starts there by itself, so no tone over it.
    assert opened == ["spotify:track:4cOdK2wGLETKBW3PvgPWqT"]
    assert window._bell.started == []


def test_a_spotify_alarm_with_no_link_still_makes_a_noise(qapp: QApplication, window: NativeWindow) -> None:
    """A best-effort link that is not there must not turn the alarm into a silent dialog."""
    window._bell = RingRecorder()
    window._ring({"name": "Wake up", "sound": "spotify"}, "")
    assert [tone for tone, _volume in window._bell.started] == ["chime"]


def test_a_spotify_alarm_falls_back_to_a_tone_when_the_link_will_not_open(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(lambda _url: False))
    window._bell = RingRecorder()
    window._ring({"name": "Wake up", "sound": "spotify"}, SPOTIFY_TRACK)
    assert [tone for tone, _volume in window._bell.started] == ["chime"]


def test_answering_an_alarm_stops_the_noise(qapp: QApplication, window: NativeWindow) -> None:
    window._bell = RingRecorder()
    QTimer.singleShot(0, lambda: window._alarm_dialog and window._alarm_dialog.accept())
    window._on_alarm({"id": "a1", "name": "Practice", "time": "07:00", "sound": "low"})
    assert [tone for tone, _volume in window._bell.started] == ["low"]
    assert window._bell.ringing is False
    assert window._bell.stops >= 1


def test_a_reminder_makes_its_sound_when_the_student_asked_for_one(
    qapp: QApplication, window: NativeWindow
) -> None:
    window._bell = RingRecorder()
    window.session.preferences = {
        **(window.session.preferences or {}),
        "reminder_sound": True,
        "alert_volume": 60,
    }
    window._present_alerts([{"title": "Essay starts soon", "body": "19:00 · Thu"}])
    assert window._bell.started == [("chime", 60)]


def test_a_reminder_is_silent_when_the_student_turned_sound_off(
    qapp: QApplication, window: NativeWindow
) -> None:
    window._bell = RingRecorder()
    window.session.preferences = {**(window.session.preferences or {}), "reminder_sound": False}
    window._present_alerts([{"title": "Essay starts soon", "body": "19:00 · Thu"}])
    assert window._bell.started == []


def test_the_end_of_session_chime_answers_to_its_own_setting(
    qapp: QApplication, window: NativeWindow
) -> None:
    """A focus notice is not a reminder: it uses the tone the phase carries and only sounds when the
    student asked for an end-of-session chime."""
    window._bell = RingRecorder()
    window.session.preferences = {
        **(window.session.preferences or {}),
        "reminder_sound": True,
        "end_chime": True,
        "alert_volume": 70,
    }
    window._present_alerts([{"title": "Focus session", "body": "Essay", "kind": "focus", "tone": "bright"}])
    assert window._bell.started == [("bright", 70)]


def test_no_chime_at_the_end_of_a_session_when_that_setting_is_off(
    qapp: QApplication, window: NativeWindow
) -> None:
    window._bell = RingRecorder()
    window.session.preferences = {
        **(window.session.preferences or {}),
        "reminder_sound": True,
        "end_chime": False,
    }
    window._present_alerts([{"title": "Break", "body": "Essay", "kind": "focus", "tone": "soft"}])
    assert window._bell.started == []


def test_a_reminder_still_rings_when_the_end_of_session_chime_is_off(
    qapp: QApplication, window: NativeWindow
) -> None:
    """The two settings are separate, so gating one on the other would silence reminders."""
    window._bell = RingRecorder()
    window.session.preferences = {
        **(window.session.preferences or {}),
        "reminder_sound": True,
        "end_chime": False,
        "alert_volume": 80,
    }
    window._present_alerts([{"title": "Essay starts soon", "body": "19:00 · Thu"}])
    assert window._bell.started == [("chime", 80)]


def test_a_reminder_rings_the_chosen_alarm_sound(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    heard = _rung(window, monkeypatch)
    window.session.preferences = {**(window.session.preferences or {}), "alarm_tone": "glass"}
    window._present_alerts([{"kind": "reminder", "title": "Math worksheet", "body": "in 10 min"}])
    assert heard == [("once", "glass")]


def test_a_spotify_sound_never_starts_music_for_a_reminder(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    heard = _rung(window, monkeypatch)
    window.session.preferences = {**(window.session.preferences or {}), "alarm_tone": "spotify"}
    window._present_alerts([{"kind": "reminder", "title": "Math worksheet", "body": "in 10 min"}])
    assert heard == [("once", "chime")]


def test_a_focus_ending_keeps_its_own_tone_until_a_sound_is_chosen(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    heard = _rung(window, monkeypatch)
    base = {**(window.session.preferences or {}), "end_chime": True}
    window.session.preferences = {key: value for key, value in base.items() if key != "alarm_tone"}
    window._present_alerts([{"kind": "focus", "title": "Break", "tone": "bright"}])
    window.session.preferences = {**window.session.preferences, "alarm_tone": "low"}
    window._present_alerts([{"kind": "focus", "title": "Break", "tone": "bright"}])
    assert heard == [("once", "bright"), ("once", "low")]


def test_an_alarm_with_no_sound_of_its_own_rings_the_chosen_one(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    heard = _rung(window, monkeypatch)
    window.session.preferences = {**(window.session.preferences or {}), "alarm_tone": "soft"}
    window._ring({"name": "Wake up"}, "")
    window._ring({"name": "Practice", "sound": "bright"}, "")
    assert heard == [("start", "soft"), ("start", "bright")]
