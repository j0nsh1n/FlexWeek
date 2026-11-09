"""What the tests and the picture of the one-time "each design has its own looks" notice share."""

from __future__ import annotations

import json

from desktop.native.window import NativeWindow
from desktop.tests.window_support import look_file

NOTICE = "New in 1.0.0: each design has its own looks."


def become_an_old_account(window: NativeWindow) -> None:
    """Model a finished account made before the designs had looks, whose device file holds no look
    choices for any design and has not seen the notice."""
    saved = json.loads(look_file().read_text())
    saved["layout"] = {"main": "classic", "day": "dial", "options": {}}
    saved.pop("new_look_notice_exempt", None)
    saved.pop("new_look_notice_seen", None)
    look_file().write_text(json.dumps(saved) + "\n")
    window.session.new_account = False
    window._load_look()


def make_legacy_account(window: NativeWindow) -> None:
    assert window.session.preferences["setup"].get("finished_at")
    become_an_old_account(window)
