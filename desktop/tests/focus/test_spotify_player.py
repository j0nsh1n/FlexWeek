"""A Spotify link plays in the student's own Spotify app, is heard or not, and stops when asked to.
Every test talks to a pretend Spotify: none may reach a real one."""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtWidgets import QApplication

    from desktop.native import spotify
    from desktop.native.spotify import LISTENING, SHOWN, STARTING
    from desktop.tests.focus.support_spotify import METADATA, PLAYLIST, TRACK, PretendSpotify, player
    from desktop.tests.waiting import wait_until


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-spotify-test"])


def opening(monkeypatch: pytest.MonkeyPatch, answer: bool = True) -> list[str]:
    opened: list[str] = []
    monkeypatch.setattr(spotify, "open_address", lambda address: opened.append(address) or answer)
    return opened


def test_a_share_link_becomes_the_apps_own_address() -> None:
    assert spotify.app_address(TRACK) == "spotify:track:4LUJzSLpBtgH3dpOH7J7Nf"
    assert spotify.app_address(PLAYLIST) == "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"
    assert spotify.app_address("https://example.com/track/abc") is None


def test_the_song_and_artists_are_read_from_spotifys_answer() -> None:
    assert spotify.read_metadata(METADATA) == (
        "Voices of the Chord",
        "Sawano Hiroyuki, mpi",
        "/com/spotify/track/4LUJzSLpBtgH3dpOH7J7Nf",
    )
    assert spotify.read_metadata("not json") == ("", "", "")
    assert spotify.playing_words("Voices of the Chord", "Sawano Hiroyuki") == (
        "Playing “Voices of the Chord” by Sawano Hiroyuki"
    )
    assert spotify.playing_words("", "") == "Playing in Spotify"


def test_a_running_spotify_is_told_to_play_and_is_heard(qapp: QApplication) -> None:
    app = PretendSpotify()
    made = player(app)
    heard: list[str] = []
    late: list[bool] = []
    made.heard.connect(heard.append)
    made.late.connect(lambda: late.append(True))
    assert made.play(TRACK) == LISTENING
    assert app.asked == ["spotify:track:4LUJzSLpBtgH3dpOH7J7Nf"]
    # Lateness is counted in the player's own polls, so a busy machine only delays the first one.
    wait_until(qapp, lambda: bool(heard), timeout=5)
    assert heard == ["Playing “Voices of the Chord” by Sawano Hiroyuki, mpi"]
    assert late == [], "heard in time, so the tone never rings"


def test_a_spotify_that_is_not_heard_lets_the_tone_ring(qapp: QApplication) -> None:
    app = PretendSpotify(plays=False)
    made = player(app)
    late: list[bool] = []
    made.late.connect(lambda: late.append(True))
    assert made.play(PLAYLIST) == LISTENING
    wait_until(qapp, lambda: late == [True], what="the player never said it was late")
    # Still not playing, so the player keeps asking until it gives up.
    wait_until(qapp, lambda: len(app.asked) >= 2, what=lambda: f"asked {len(app.asked)} times")
    made.stop()


def test_a_spotify_that_is_not_open_is_started_then_told_to_play(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened = opening(monkeypatch)
    app = PretendSpotify(running=False, starts_after=3)
    made = player(app)
    heard: list[str] = []
    made.heard.connect(heard.append)
    assert made.play(PLAYLIST) == LISTENING
    assert opened == ["spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"], "opening its address starts the app"
    assert app.asked == []
    wait_until(qapp, lambda: bool(app.asked), what="the app was never told to play")
    assert app.asked == ["spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"], "and once it is up, it is told to play"
    wait_until(qapp, lambda: bool(heard), what="the playlist was never heard")


def test_stopping_pauses_what_flexweek_started_and_only_that(qapp: QApplication) -> None:
    app = PretendSpotify()
    made = player(app)
    made.stop()
    assert app.paused == 0, "nothing was started, so the student's own music is left alone"
    made.play(TRACK)
    made.stop()
    assert app.paused == 1


def test_where_spotify_cannot_be_asked_a_track_is_opened_and_a_playlist_needs_the_tone(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows: a track starts by itself when opened in the app, and the Stop key stops it. A playlist
    does not start, so it is only shown."""
    opened = opening(monkeypatch)
    keys: list[str] = []
    made = player(spotify.NoRemote(), keys)
    assert made.play(TRACK) == STARTING
    made.stop()
    assert keys == ["stop"]
    assert made.play(PLAYLIST) == SHOWN
    made.stop()
    assert keys == ["stop"], "the Stop key is not pressed for what FlexWeek did not start"
    assert opened == ["spotify:track:4LUJzSLpBtgH3dpOH7J7Nf", "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"]


def test_without_the_spotify_app_the_link_goes_to_the_browser_and_does_not_count_as_playing(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[str] = []
    monkeypatch.setattr(
        spotify, "open_address", lambda address: opened.append(address) or address.startswith("https:")
    )
    made = player(spotify.NoRemote())
    assert made.play(TRACK) == SHOWN
    assert opened == ["spotify:track:4LUJzSLpBtgH3dpOH7J7Nf", TRACK]


def test_on_linux_without_the_spotify_app_the_browser_gets_the_link_and_the_tone_rings(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bus is there but no Spotify is on it, and nothing takes its address: a browser tab, which
    will not play by itself, so the alarm is not counted as heard."""
    opened: list[str] = []
    monkeypatch.setattr(
        spotify, "open_address", lambda address: opened.append(address) or address.startswith("https:")
    )
    made = player(PretendSpotify(running=False))
    assert made.play(TRACK) == SHOWN
    assert opened == ["spotify:track:4LUJzSLpBtgH3dpOH7J7Nf", TRACK]
