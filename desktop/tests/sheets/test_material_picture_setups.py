"""The pictures added for the Material review put the window in the state they say, and the delete-account
picture names one account in both places."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import named, pump
from desktop.tests.pictures import _sheets_g20, screens_sheets_5b
from desktop.tests.window_support import USERNAME, qapp  # noqa: F401

NEW_SCREENS = {
    "sheets.material_duplicate_preview": "previewSheet",
    "account.material_recovery_save_prompt": "recoveryPrompt",
    "sheets.material_delete_block_cards_prompt": "sheetPrompt",
    "sheets.material_replace_week_prompt": "sheetPrompt",
    "sheets.material_before_planning_stacked": "sheetPrompt",
    "sheets.material_restore_prompt": "sheetPrompt",
}


@pytest.mark.parametrize("screen_id", list(NEW_SCREENS))
def test_each_new_picture_puts_its_sheet_on_screen(qapp, window, screen_id: str) -> None:
    screen = next(item for item in _sheets_g20.SCREENS if item.id == screen_id)
    screen.prepare(window)
    pump(qapp, 20)
    items = named(window._material_page.root, NEW_SCREENS[screen_id])
    assert [item for item in items if item.property("visible")], screen_id


def test_the_delete_account_picture_signs_in_the_account_it_asks_about() -> None:
    assert screens_sheets_5b.STORAGE["username"] == USERNAME
