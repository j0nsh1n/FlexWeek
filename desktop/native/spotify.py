"""Spotify songs and playlists, played in the student's own Spotify app rather than a browser tab.

Spotify's rules leave one way to play whole songs for everyone: ask their Spotify app to. An embedded
player plays 30-second previews inside an app's own browser, and the Web API is limited to five named
users an app. So a share link becomes Spotify's own address for the same thing, handed to the app.

On Linux the app answers on the session bus as an MPRIS media player, so FlexWeek tells it to play,
hears back when it is playing, and pauses it when the alarm stops. On Windows it can only open the
address: a track then starts by itself when nothing else is playing, and a playlist never does.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices

SHARE = re.compile(
    r"https://open\.spotify\.com/(track|playlist|album|episode|show)/([A-Za-z0-9]+)/?(?:[?#].*)?"
)
SPOTIFY_BUS = "org.mpris.MediaPlayer2.spotify"
MPRIS_PATH = "/org/mpris/MediaPlayer2"
PLAYER = "org.mpris.MediaPlayer2.Player"
PROPERTIES = "org.freedesktop.DBus.Properties"
# How long Spotify gets to be heard before the alarm's own tone rings as well, how long one that had
# to be started gets before FlexWeek stops listening for it, and how often it asks meanwhile.
GRACE_MS, GIVE_UP_MS, POLL_MS = 1500, 20000, 250
# A Spotify that has only just started can miss the first request to play, so it is asked again.
ASK_AGAIN_MS = 2000

# What `play` managed. LISTENING: FlexWeek will say when it is heard. STARTING: opened in the app,
# where a track starts by itself. SHOWN: opened, but nothing will play until the student presses
# play, as with a playlist on Windows or a link that could only go to the browser.
LISTENING, STARTING, SHOWN = "listening", "starting", "shown"


def app_address(url: str) -> str | None:
    """`https://open.spotify.com/track/ID?si=...` as the app's own `spotify:track:ID`."""
    found = SHARE.fullmatch(url or "")
    return f"spotify:{found.group(1)}:{found.group(2)}" if found else None


def open_address(address: str) -> bool:
    return QDesktopServices.openUrl(QUrl(address))


def open_in_app(url: str) -> bool:
    """Open a share link in the Spotify app, or in the browser where there is no app to take it."""
    address = app_address(url)
    return bool(address and open_address(address)) or open_address(url)


def playing_words(title: str, artist: str) -> str:
    if title and artist:
        return f"Playing “{title}” by {artist}"
    return f"Playing “{title}”" if title else "Playing in Spotify"


def read_metadata(text: str) -> tuple[str, str, str]:
    """Title, artists and track id from busctl's JSON for an MPRIS Metadata map."""
    try:
        data = json.loads(text)["data"]
    except ValueError, KeyError, TypeError:
        return "", "", ""
    if not isinstance(data, dict):
        return "", "", ""

    def field(key: str) -> object:
        entry = data.get(key)
        return entry.get("data") if isinstance(entry, dict) else None

    artists = field("xesam:artist")
    artist = ", ".join(str(name) for name in artists) if isinstance(artists, list) else str(artists or "")
    return str(field("xesam:title") or ""), artist, str(field("mpris:trackid") or "")


class Remote(Protocol):
    """The student's Spotify app, as far as FlexWeek can reach it."""

    def reachable(self) -> bool: ...
    def running(self) -> bool: ...
    def play(self, address: str) -> None: ...
    def playing(self) -> bool: ...
    def pause(self) -> None: ...
    def now_playing(self) -> tuple[str, str, str]: ...


class NoRemote:
    """Where there is no session bus to ask, as on Windows: FlexWeek can only open the address."""

    def reachable(self) -> bool:
        return False

    def running(self) -> bool:
        return False

    def play(self, address: str) -> None:
        return None

    def playing(self) -> bool:
        return False

    def pause(self) -> None:
        return None

    def now_playing(self) -> tuple[str, str, str]:
        return "", "", ""


class MprisRemote:
    """The Spotify app on the Linux session bus."""

    def __init__(self, service: str = SPOTIFY_BUS) -> None:
        from PySide6.QtDBus import QDBusConnection

        self._service = service
        bus = QDBusConnection.sessionBus()
        self._bus = bus if bus.isConnected() else None

    def reachable(self) -> bool:
        return self._bus is not None

    def running(self) -> bool:
        if self._bus is None:
            return False
        reply = self._bus.interface().isServiceRegistered(self._service)
        return bool(reply.isValid() and reply.value())

    def _call(self, interface: str, method: str, *arguments: object) -> list:
        from PySide6.QtDBus import QDBusInterface

        if self._bus is None:
            return []
        return (
            QDBusInterface(self._service, MPRIS_PATH, interface, self._bus)
            .call(method, *arguments)
            .arguments()
        )

    def play(self, address: str) -> None:
        self._call(PLAYER, "OpenUri", address)

    def pause(self) -> None:
        self._call(PLAYER, "Pause")

    def playing(self) -> bool:
        answer = self._call(PROPERTIES, "Get", PLAYER, "PlaybackStatus")
        status = answer[0] if answer else ""
        status = status.variant() if hasattr(status, "variant") else status
        return status == "Playing"

    def now_playing(self) -> tuple[str, str, str]:
        """Qt for Python cannot unpack the metadata map, so busctl reads it where it is installed.
        Without it the alarm says only that Spotify is playing."""
        busctl = shutil.which("busctl")
        if busctl is None:
            return "", "", ""
        command = [
            busctl,
            "--user",
            "--json=short",
            "get-property",
            self._service,
            MPRIS_PATH,
            PLAYER,
            "Metadata",
        ]
        try:
            done = subprocess.run(command, capture_output=True, text=True, timeout=1, check=False)
        except OSError, subprocess.SubprocessError:
            return "", "", ""
        return read_metadata(done.stdout)


def system_remote() -> Remote:
    return MprisRemote() if sys.platform.startswith("linux") else NoRemote()


def press_media_stop() -> None:
    """Windows' media Stop key. It never starts anything, so at worst it stops what is playing, and
    stopping is what dismissing an alarm means."""
    if sys.platform != "win32":
        return
    import ctypes

    stop, released = 0xB2, 0x0002
    keys = ctypes.windll.user32  # type: ignore[attr-defined]
    keys.keybd_event(stop, 0, 0, 0)
    keys.keybd_event(stop, 0, released, 0)


class SpotifyPlayer(QObject):
    """Plays a share link in the student's Spotify app, and says whether it is heard."""

    # Spotify is playing it: "Playing “Title” by Artist", or just that it is playing.
    heard = Signal(str)
    # Not heard within the grace. An alarm rings its own tone meanwhile, so it is never silent.
    late = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
        remote: Remote | None = None,
        stop_key: Callable[[], None] = press_media_stop,
    ) -> None:
        super().__init__(parent)
        self._remote = remote if remote is not None else system_remote()
        self._stop_key = stop_key
        self.grace_ms, self.give_up_ms, self.poll_ms = GRACE_MS, GIVE_UP_MS, POLL_MS
        self.ask_again_ms = ASK_AGAIN_MS
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check)
        self._address: str | None = None
        self._waited = 0
        self._asked_at: int | None = None
        self._late_said = False
        # What stopping has to undo: FlexWeek asked the app to play, or opened a track that plays.
        self._started = False
        self._key_stops_it = False

    def play(self, url: str) -> str:
        """Start `url` in Spotify. LISTENING, STARTING or SHOWN, or "" when nothing could open it."""
        self.stop()
        address = app_address(url)
        if address is None:
            return ""
        if self._remote.reachable():
            self._address, self._waited, self._late_said = address, 0, False
            if self._remote.running():
                self._ask()
            elif not open_address(address):
                # No app to start: the browser, which will not play by itself.
                return SHOWN if open_address(url) else ""
            self._started = True
            self._timer.start(self.poll_ms)
            return LISTENING
        if open_address(address):
            if address.startswith("spotify:track:"):
                self._key_stops_it = True
                return STARTING
            return SHOWN
        return SHOWN if open_address(url) else ""

    def stop(self) -> None:
        """Stop listening, and pause what FlexWeek started. Music the student had on stays as it was
        when FlexWeek never asked the app for anything."""
        self._timer.stop()
        if self._started:
            self._remote.pause()
        elif self._key_stops_it:
            self._stop_key()
        self._started = self._key_stops_it = False
        self._address, self._asked_at = None, None

    def _ask(self) -> None:
        if self._address is not None:
            self._remote.play(self._address)
            self._asked_at = self._waited

    def _check(self) -> None:
        self._waited += self.poll_ms
        running = self._remote.running()
        if running and self._asked_at is None:
            # Started by opening its address, and now up to be asked.
            self._ask()
        elif running and self._remote.playing():
            self._timer.stop()
            title, artist, _track = self._remote.now_playing()
            self.heard.emit(playing_words(title, artist))
            return
        elif running and self._asked_at is not None and self._waited - self._asked_at >= self.ask_again_ms:
            self._ask()
        if not self._late_said and self._waited >= self.grace_ms:
            self._late_said = True
            self.late.emit()
        if self._waited >= self.give_up_ms:
            self._timer.stop()
