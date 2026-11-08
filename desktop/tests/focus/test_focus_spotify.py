"""The Settings Spotify link is the only one the desktop plays, including when focus starts."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.light_app import open_light  # noqa: E402,F401
from desktop.tests.test_reminders_window import TRACK, add_practice  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-focus-spotify-test"])


@pytest.fixture()
def window(open_light: Callable[..., NativeWindow]) -> NativeWindow:  # noqa: F811
    """The light window, signed in on the week at the size a new window has."""
    return open_light()


def practice(qapp: QApplication, made: NativeWindow, **extra: object) -> None:
    """Guitar practice on Thursday, saved, with every refresh the save started landed, so none can
    replace the preferences a test sets by hand."""
    add_practice(qapp, made, **extra)
    session = made.session
    wait_until(
        qapp, lambda: not session.busy and not session.dirty and not getattr(session.client, "pending", 0)
    )


def choose(made: NativeWindow, **preferences: object) -> None:
    made.session.preferences = {**(made.session.preferences or {}), **preferences}


def test_open_spotify_uses_the_settings_link_not_the_block(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []
    monkeypatch.setattr("desktop.native.window.open_in_app", lambda url: asked.append(url) or True)
    practice(qapp, window, spotify_url=TRACK)
    window.session.select_block("practice", 3)
    choose(window, default_spotify_url=None)
    window._sync_more_menu()
    assert window._spotify_action is not None
    assert window._spotify_action.isVisible() is False
    window._open_spotify()
    assert window.session.message == "Add a Spotify link in Settings, under Alerts."
    choose(window, default_spotify_url=TRACK)
    window._sync_more_menu()
    assert window._spotify_action.isVisible() is True
    window._open_spotify()
    assert asked == [TRACK]


def test_focus_off_does_not_open_spotify(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []
    monkeypatch.setattr("desktop.native.spotify.open_in_app", lambda url: asked.append(url) or True)
    practice(qapp, window)
    choose(window, focus_audio="off", default_spotify_url=TRACK)
    assert window.session.start_focus("practice", 3) is True
    assert window.session.focus is not None
    assert asked == []


def test_focus_spotify_opens_the_settings_link(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []
    monkeypatch.setattr("desktop.native.spotify.open_in_app", lambda url: asked.append(url) or True)
    practice(qapp, window, spotify_url="https://open.spotify.com/track/1301WleyT98MSxVHPZCA6M")
    choose(window, focus_audio="spotify", default_spotify_url=TRACK)
    assert window.session.start_focus("practice", 3) is True
    assert window.session.focus is not None
    assert asked == [TRACK]


def test_focus_spotify_without_a_link_says_so_and_still_starts(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []
    monkeypatch.setattr("desktop.native.spotify.open_in_app", lambda url: asked.append(url) or True)
    practice(qapp, window)
    choose(window, focus_audio="spotify", default_spotify_url=None)
    assert window.session.start_focus("practice", 3) is True
    assert window.session.focus is not None
    assert asked == []
    assert window.session.message == "Add a Spotify link in Settings, under Alerts. Focus has started."


def test_focus_spotify_carries_on_when_the_app_does_not_open(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("desktop.native.spotify.open_in_app", lambda _url: False)
    practice(qapp, window)
    choose(window, focus_audio="spotify", default_spotify_url=TRACK)
    assert window.session.start_focus("practice", 3) is True
    assert window.session.focus is not None
    assert window.session.message == "Spotify didn't open. Focus has started."


def test_focus_rain_is_stored_and_stays_quiet(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []
    monkeypatch.setattr("desktop.native.spotify.open_in_app", lambda url: asked.append(url) or True)
    practice(qapp, window)
    choose(window, focus_audio="rain", default_spotify_url=TRACK)
    assert window.session.start_focus("practice", 3) is True
    assert asked == []
