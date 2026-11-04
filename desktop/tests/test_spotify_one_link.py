"""The Settings Spotify link is the only one the desktop plays, including when focus starts."""

from __future__ import annotations

import contextlib
import importlib.util
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QStandardPaths
    from PySide6.QtWidgets import QApplication, QLabel

    from desktop.native.settings import FOCUS_AUDIO_NOTE, SettingsPage
    from desktop.native.window import NativeWindow
    from desktop.tests.test_reminders_window import TRACK, add_practice, launch, serve


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-spotify-one-link"])


@pytest.fixture()
def database(tmp_path: Path) -> Path:
    return tmp_path / "spotify-one-link.db"


@pytest.fixture()
def opened(qapp: QApplication) -> Iterator[list]:
    things: list = []
    yield things
    for thing in reversed(things):
        if isinstance(thing, NativeWindow):
            with contextlib.suppress(RuntimeError):
                thing.session.client.reset()
            thing.hide()
        else:
            thing.stop()
    qapp.processEvents()


def test_focus_offers_every_sound_and_saves_the_one_chosen(qapp: QApplication) -> None:
    page = SettingsPage(None, {"alarms": [], "focus_audio": "rain"}, {}, {})
    try:
        offered = [page.focus_audio.itemData(index) for index in range(page.focus_audio.count())]
        assert offered == ["off", "rain", "lo-fi", "white-noise", "spotify"]
        note = page.findChild(QLabel, "prefFocusAudioNote")
        assert isinstance(note, QLabel) and note.text() == FOCUS_AUDIO_NOTE
        assert page.updates()["focus_audio"] == "rain"
        for choice in ("lo-fi", "white-noise", "spotify", "off"):
            page.focus_audio.setCurrentIndex(page.focus_audio.findData(choice))
            assert page.updates()["focus_audio"] == choice
    finally:
        page.close()


def test_open_spotify_uses_the_settings_link_not_the_block(
    qapp: QApplication, database, opened, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []
    monkeypatch.setattr("desktop.native.window.open_in_app", lambda url: asked.append(url) or True)
    window = launch(qapp, serve(database, opened), "listener", opened, create=True)
    add_practice(qapp, window, spotify_url=TRACK)
    window.session.select_block("practice", 3)
    window.session.preferences = {**(window.session.preferences or {}), "default_spotify_url": None}
    window._sync_more_menu()
    assert window._spotify_action is not None
    assert window._spotify_action.isVisible() is False
    window._open_spotify()
    assert window.session.message == "Add a Spotify link in Settings, under Alerts."
    window.session.preferences = {**(window.session.preferences or {}), "default_spotify_url": TRACK}
    window._sync_more_menu()
    assert window._spotify_action.isVisible() is True
    window._open_spotify()
    assert asked == [TRACK]


def test_focus_off_does_not_open_spotify(
    qapp: QApplication, database, opened, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []
    monkeypatch.setattr("desktop.native.spotify.open_in_app", lambda url: asked.append(url) or True)
    window = launch(qapp, serve(database, opened), "quiet_focus", opened, create=True)
    add_practice(qapp, window)
    window.session.preferences = {
        **(window.session.preferences or {}),
        "focus_audio": "off",
        "default_spotify_url": TRACK,
    }
    assert window.session.start_focus("practice", 3) is True
    assert window.session.focus is not None
    assert asked == []


def test_focus_spotify_opens_the_settings_link(
    qapp: QApplication, database, opened, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []
    monkeypatch.setattr("desktop.native.spotify.open_in_app", lambda url: asked.append(url) or True)
    window = launch(qapp, serve(database, opened), "study_mix", opened, create=True)
    add_practice(qapp, window, spotify_url="https://open.spotify.com/track/1301WleyT98MSxVHPZCA6M")
    window.session.preferences = {
        **(window.session.preferences or {}),
        "focus_audio": "spotify",
        "default_spotify_url": TRACK,
    }
    assert window.session.start_focus("practice", 3) is True
    assert window.session.focus is not None
    assert asked == [TRACK]


def test_focus_spotify_without_a_link_says_so_and_still_starts(
    qapp: QApplication, database, opened, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []
    monkeypatch.setattr("desktop.native.spotify.open_in_app", lambda url: asked.append(url) or True)
    window = launch(qapp, serve(database, opened), "no_link", opened, create=True)
    add_practice(qapp, window)
    window.session.preferences = {
        **(window.session.preferences or {}),
        "focus_audio": "spotify",
        "default_spotify_url": None,
    }
    assert window.session.start_focus("practice", 3) is True
    assert window.session.focus is not None
    assert asked == []
    assert window.session.message == "Add a Spotify link in Settings, under Alerts. Focus has started."


def test_focus_spotify_carries_on_when_the_app_does_not_open(
    qapp: QApplication, database, opened, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("desktop.native.spotify.open_in_app", lambda _url: False)
    window = launch(qapp, serve(database, opened), "no_app", opened, create=True)
    add_practice(qapp, window)
    window.session.preferences = {
        **(window.session.preferences or {}),
        "focus_audio": "spotify",
        "default_spotify_url": TRACK,
    }
    assert window.session.start_focus("practice", 3) is True
    assert window.session.focus is not None
    assert window.session.message == "Spotify didn't open. Focus has started."


def test_focus_rain_is_stored_and_stays_quiet(
    qapp: QApplication, database, opened, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []
    monkeypatch.setattr("desktop.native.spotify.open_in_app", lambda url: asked.append(url) or True)
    window = launch(qapp, serve(database, opened), "rain_later", opened, create=True)
    add_practice(qapp, window)
    window.session.preferences = {
        **(window.session.preferences or {}),
        "focus_audio": "rain",
        "default_spotify_url": TRACK,
    }
    assert window.session.start_focus("practice", 3) is True
    assert asked == []
