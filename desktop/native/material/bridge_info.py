"""What Material's Help, About and Update sheets show. The words and the key list are the Widgets
dialogs' own (settings_copy); this module only turns them into the form QML reads."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QUrl

from desktop.native.settings_copy import (
    ABOUT_HERE,
    ABOUT_LINE,
    HELP_PLANNING,
    HELP_SCREENS,
    first_lines,
    help_keys,
    key_parts,
    keys_words,
)
from desktop.native.version import VERSION

LOGO = Path(__file__).resolve().parents[2] / "assets" / "logo.png"
SIGN_OUT = {
    "id": "sign-out",
    "title": "Sign out",
    "answers": [
        {"id": "stay", "label": "Cancel", "kind": "text", "default": True},
        {"id": "yes", "label": "Sign out", "kind": "filled"},
    ],
}


def help_form(numbers: bool, letters: bool) -> dict[str, Any]:
    """Help: how planning works, the four screens, and the keys as this look answers to them."""
    return {
        "heading": "Help",
        "planning": HELP_PLANNING,
        "screens": [{"name": name, "words": words} for name, words in HELP_SCREENS],
        "keys": [
            {
                "words": what,
                "spoken": keys_words(marked),
                "parts": [{"text": text, "cap": cap} for text, cap in key_parts(marked)],
            }
            for marked, what in help_keys(numbers, letters, material=True)
        ],
    }


def about_form(storage: dict | None) -> dict[str, Any]:
    """About: the version, what FlexWeek is, and where the week is saved."""
    hosted = (storage or {}).get("mode") == "hosted"
    where = (
        "Your week is saved on your FlexWeek server, "
        f"{(storage or {}).get('origin') or ''}, under this account."
        if hosted
        else ABOUT_HERE
    )
    return {
        "heading": "About FlexWeek",
        "logo": QUrl.fromLocalFile(str(LOGO)).toString(),
        "version": f"FlexWeek {VERSION}",
        "what": ABOUT_LINE,
        "where": where,
        "folder": not hosted,
    }


def update_form(update: dict, current: str, state: dict) -> dict[str, Any]:
    """The update sheet: what is ready, what changed, and how the download is going."""
    return {
        "heading": f"FlexWeek {update['version']} is ready",
        "detail": f"You have {current}. Updating keeps your account and your weeks.",
        "notes": first_lines(update.get("notes") or ""),
        "status": state["status"],
        "problem": state["problem"],
        "busy": state["busy"],
        "progress": state["progress"],
    }
