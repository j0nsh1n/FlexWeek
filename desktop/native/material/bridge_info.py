"""What Material's Help, About and Update sheets show. The words and the key list are the Widgets
dialogs' own (settings_copy); this module only turns them into the form QML reads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import flexweek_engine  # type: ignore[import-untyped]
from PySide6.QtCore import QUrl

from desktop.native.version import VERSION

LOGO = Path(__file__).resolve().parents[2] / "assets" / "logo.png"
SIGN_OUT: dict[str, Any] = json.loads(flexweek_engine.VIEW_SIGN_OUT_JSON)


def help_form(numbers: bool, letters: bool) -> dict[str, Any]:
    """Help: how planning works, the four screens, and the keys as this look answers to them."""
    return json.loads(flexweek_engine.views_help_form(numbers, letters))


def about_form(storage: dict | None) -> dict[str, Any]:
    """About: the version, what FlexWeek is, and where the week is saved (always this computer)."""
    logo_url = QUrl.fromLocalFile(str(LOGO)).toString()
    return json.loads(flexweek_engine.views_about_form(json.dumps(storage), logo_url, VERSION))


def update_form(update: dict, current: str, state: dict) -> dict[str, Any]:
    """The update sheet: what is ready, what changed, and how the download is going."""
    return json.loads(
        flexweek_engine.views_update_form(json.dumps(update), str(current), json.dumps(state))
    )
