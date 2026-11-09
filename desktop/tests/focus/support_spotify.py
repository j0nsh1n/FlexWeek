"""A pretend Spotify app and a player wired to it, for the Spotify tests in this folder."""

from __future__ import annotations

from typing import Any

from desktop.native import spotify
from desktop.native.spotify import SpotifyPlayer

TRACK = "https://open.spotify.com/track/4LUJzSLpBtgH3dpOH7J7Nf?si=abc123"
PLAYLIST = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
METADATA = (
    '{"type":"a{sv}","data":{"mpris:trackid":{"type":"s","data":"/com/spotify/track/4LUJzSLpBtgH3dpOH7J7Nf"},'
    '"xesam:title":{"type":"s","data":"Voices of the Chord"},'
    '"xesam:artist":{"type":"as","data":["Sawano Hiroyuki","mpi"]}}}'
)


class PretendSpotify:
    """The Spotify app on the session bus, as far as FlexWeek can see it."""

    def __init__(self, running: bool = True, plays: bool = True, starts_after: int = 0) -> None:
        self.is_running, self.plays, self.starts_after = running, plays, starts_after
        self.asked: list[str] = []
        self.paused = 0
        self._is_playing = False

    def reachable(self) -> bool:
        return True

    def running(self) -> bool:
        if not self.is_running and self.starts_after:
            self.starts_after -= 1
            self.is_running = self.starts_after == 0
        return self.is_running

    def play(self, address: str) -> None:
        self.asked.append(address)
        self._is_playing = self.plays

    def playing(self) -> bool:
        return self._is_playing

    def pause(self) -> None:
        self.paused += 1
        self._is_playing = False

    def now_playing(self) -> tuple[str, str, str]:
        return spotify.read_metadata(METADATA)


def player(remote: Any, keys: list[str] | None = None) -> SpotifyPlayer:
    made = SpotifyPlayer(remote=remote, stop_key=lambda: (keys if keys is not None else []).append("stop"))
    made.grace_ms, made.give_up_ms, made.poll_ms, made.ask_again_ms = 120, 600, 20, 60
    return made
