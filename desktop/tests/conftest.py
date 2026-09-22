"""What every desktop test shares."""

from __future__ import annotations

import importlib.util
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def nothing_leaves_the_test(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """No test reaches this computer's own apps. A Spotify alarm tells the Spotify app to play, over
    the session bus or by opening its address, and the developer's Spotify was running: a test would
    have started music. A test that wants to see what would be opened patches over this."""
    if importlib.util.find_spec("PySide6") is not None:
        from PySide6.QtGui import QDesktopServices

        from desktop.native import spotify

        monkeypatch.setattr(spotify, "system_remote", spotify.NoRemote)
        monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(lambda _url: False))
    yield
