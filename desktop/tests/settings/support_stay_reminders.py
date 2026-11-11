"""What the tests of reminders kept on screen share: the words, and a tray that shows no messages."""

from __future__ import annotations

SOON = "Guitar practice starts soon — 6:45 PM · Thu"
NOW = "Guitar practice starts now — 6:45 PM · Thu"


class QuietTray:
    """A tray on a desktop that cannot show messages."""

    def supportsMessages(self) -> bool:  # noqa: N802
        return False

    def showMessage(self, *_rest: object) -> None:  # noqa: N802
        raise AssertionError("a tray that shows no messages was asked to show one")

    def isVisible(self) -> bool:  # noqa: N802
        return True

    def hide(self) -> None:
        return None
