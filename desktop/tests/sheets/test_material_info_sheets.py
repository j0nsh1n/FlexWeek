# ruff: noqa: F811
"""Help, About, Update and the Sign out question as Material sheets (1.5.0 step 5a). Each opens from its More
row, key or signal, shows what its Widgets dialog showed, does the same thing, and the Widgets dialog never
opens over Material. Expected words are the Widgets copy (settings_copy) and the requirement, not what the
sheet prints."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtQml import QQmlProperty
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.settings_copy import (
    ABOUT_HERE,
    ABOUT_LINE,
    HELP_PLANNING,
    HELP_PLANNING_MATERIAL,
    HELP_SCREENS,
    first_lines,
    help_keys,
    keys_words,
)
from desktop.native.version import VERSION
from desktop.native.window import SIGN_OUT_QUESTION, NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.material_support import focus_quick, named, pump, quick_of, quick_window_of, show_material
from desktop.tests.window_support import look_file, qapp  # noqa: F401

NOTES = "## What changed\n- Material 3 is the one look.\n- Fewer pop-ups.\n\nMore detail below."
UPDATE = {"version": "1.5.0", "notes": NOTES}


def _sheets(window: NativeWindow):
    return window._material_page.bridge.sheets


def _material(qapp: QApplication, window: NativeWindow) -> tuple[QObject, object]:
    root = show_material(qapp, window)
    quick = quick_of(window)
    window.activateWindow()
    focus_quick(window)
    pump(qapp)
    return root, quick


def _one(root: QObject, name: str) -> QObject:
    found = named(root, name)
    assert len(found) == 1, f"{name}: {len(found)} found"
    return found[0]


def _text(root: QObject, name: str) -> str:
    return str(_one(root, name).property("text"))


def _focused(window: NativeWindow) -> str:
    item = quick_window_of(window).activeFocusItem()
    return "" if item is None else str(item.objectName())


def _press(quick, key: Qt.Key) -> None:
    QTest.keyClick(quick, key)
    pump(QApplication.instance(), 20)


def _click(quick, item: QObject) -> None:
    spot = item.mapToScene(item.boundingRect().center())
    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, pos=spot.toPoint())
    pump(QApplication.instance(), 20)


# Help


def test_help_opens_from_its_more_row_as_a_sheet_with_the_widgets_content(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, quick = _material(qapp, window)
    _sheets(window).moreAction("helpButton")
    pump(qapp, 40)
    assert _sheets(window).property("kind") == "help"
    assert _text(root, "helpPlanning") == HELP_PLANNING_MATERIAL
    assert "Ctrl+K" not in HELP_PLANNING_MATERIAL and "command bar" not in HELP_PLANNING_MATERIAL
    assert HELP_PLANNING_MATERIAL.endswith("Details says why.")
    assert "Ctrl+K" in HELP_PLANNING, "the Widgets Help keeps its own sentence"
    cards = named(root, "helpScreen")
    assert len(cards) == len(HELP_SCREENS)
    for card, (name, words) in zip(cards, HELP_SCREENS, strict=True):
        spoken = [str(kid.property("text")) for kid in card.childItems()[0].childItems()]
        assert spoken == [name, words]
    bridge = window._material_page.bridge
    wanted = [keys_words(key) for key, _ in help_keys(bridge.shortcuts, bridge.letterKeys, material=True)]
    assert [row["spoken"] for row in _sheets(window).property("form")["keys"]] == wanted
    assert len(named(root, "helpKey")) == len(wanted)


def test_f1_opens_help_and_esc_closes_it_and_the_keyboard_goes_back(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, quick = _material(qapp, window)
    fab = _one(root, "materialFab")
    fab.forceActiveFocus()
    pump(qapp)
    _press(quick, Qt.Key.Key_F1)
    assert _sheets(window).property("kind") == "help"
    assert _focused(window) == "helpClose", "the keyboard starts on Close"
    _press(quick, Qt.Key.Key_Escape)
    assert _sheets(window).property("kind") == ""
    assert quick_window_of(window).activeFocusItem() is fab


def test_help_closes_from_its_close_button_and_scrolls_from_the_keyboard(
    qapp: QApplication, window: NativeWindow
) -> None:
    root, quick = _material(qapp, window)
    _sheets(window).openHelp()
    pump(qapp, 40)
    body = _one(root, "sheetBody")
    assert float(body.property("contentY")) == 0
    _press(quick, Qt.Key.Key_PageDown)
    assert float(body.property("contentY")) > 0, "Page Down scrolls a sheet longer than the window"
    _press(quick, Qt.Key.Key_PageUp)
    assert float(body.property("contentY")) == 0
    _click(quick, _one(root, "helpClose"))
    assert _sheets(window).property("kind") == ""


def _spoken(window: NativeWindow) -> list[str]:
    return [row["spoken"] for row in _sheets(window).property("form")["keys"]]


def _help_keys(qapp: QApplication, window: NativeWindow, **material: bool) -> list[str]:
    look_file().write_text(json.dumps({"material": material}))
    show_material(qapp, window)
    window._material_page.publish()
    pump(qapp)
    _sheets(window).openHelp()
    pump(qapp, 20)
    rows = _spoken(window)
    _sheets(window).closeSheet()
    return rows


def test_help_in_material_lists_the_keys_material_answers_to(
    qapp: QApplication, window: NativeWindow
) -> None:
    rows = _help_keys(qapp, window)
    assert "1 to 5" in rows and "D W M" not in rows
    assert "Ctrl+Z" in rows and "Ctrl+Y or Ctrl+Shift+Z" in rows and "Ctrl+S" in rows
    assert "Ctrl+Shift+F" in rows
    for key in ("F1", "Ctrl+N", "Ctrl+Shift+L", "Ctrl+D", "Delete", "Ctrl+C then Ctrl+V"):
        assert key in rows, key
    for key in ("T", "B or Esc", "Ctrl+K", "Esc while dragging"):
        assert key not in rows, key


def test_help_follows_the_number_and_letter_switches(qapp: QApplication, window: NativeWindow) -> None:
    rows = _help_keys(qapp, window, letters=True)
    for key in ("1 to 5", "T", "D W M", "J K", "C", "P", "Z", "F"):
        assert key in rows, key
    rows = _help_keys(qapp, window, shortcuts=False)
    assert "1 to 5" not in rows and "D W M" not in rows
    rows = _help_keys(qapp, window, shortcuts=False, letters=True)
    assert "1 to 5" not in rows and "D W M" in rows




# About


def test_about_opens_from_its_more_row_with_the_version_and_where_the_week_is_saved(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, quick = _material(qapp, window)
    window.session.storage_info = {"mode": "local"}
    _sheets(window).moreAction("aboutButton")
    pump(qapp, 40)
    assert _sheets(window).property("kind") == "about"
    assert _text(root, "aboutVersion") == f"FlexWeek {VERSION}"
    assert _text(root, "aboutWhat") == ABOUT_LINE
    assert _text(root, "aboutWhere") == ABOUT_HERE
    assert _one(root, "aboutOpenFolder").property("visible") is True


def test_about_open_folder_opens_the_folder_the_week_lives_in(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[QUrl] = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url) or True)
    root, quick = _material(qapp, window)
    window.session.storage_info = {"mode": "local"}
    _sheets(window).openAbout()
    pump(qapp, 40)
    _click(quick, _one(root, "aboutOpenFolder"))
    assert opened == [QUrl.fromLocalFile(str(window._look_path().parent))]


def test_about_closes_with_esc_and_the_keyboard_goes_back(qapp: QApplication, window: NativeWindow) -> None:
    root, quick = _material(qapp, window)
    fab = _one(root, "materialFab")
    fab.forceActiveFocus()
    pump(qapp)
    _sheets(window).openAbout()
    pump(qapp, 40)
    assert _focused(window) == "aboutClose"
    _press(quick, Qt.Key.Key_Escape)
    assert _sheets(window).property("kind") == ""
    assert quick_window_of(window).activeFocusItem() is fab




# Update


class _Download:
    def __init__(self) -> None:
        self.asked: list[dict] = []

    def __call__(self, update: dict) -> None:
        self.asked.append(update)


def _update_rig(window: NativeWindow, monkeypatch: pytest.MonkeyPatch) -> _Download:
    download = _Download()
    monkeypatch.setattr(window._updater, "download", download)
    window._updates = {}
    monkeypatch.setattr(window, "_save_look", lambda: None)
    return download


def test_an_update_found_shows_a_material_sheet_with_what_changed(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _update_rig(window, monkeypatch)
    root, quick = _material(qapp, window)
    window._update_asked = True
    window._on_update_found(UPDATE)
    pump(qapp, 40)
    assert _sheets(window).property("kind") == "update"
    assert _text(root, "sheetTitle") == "FlexWeek 1.5.0 is ready"
    assert _text(root, "updateDetail") == f"You have {VERSION}. Updating keeps your account and your weeks."
    wanted = "What changed\n•  Material 3 is the one look.\n•  Fewer pop-ups.\nMore detail below."
    assert _text(root, "updateNotes") == wanted
    assert _text(root, "updateNotes") == first_lines(NOTES)
    assert _focused(window) == "updateInstall"


def test_update_now_starts_the_download_and_shows_progress_and_problems(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    download = _update_rig(window, monkeypatch)
    root, quick = _material(qapp, window)
    window._update_asked = True
    window._on_update_found(UPDATE)
    pump(qapp, 40)
    _click(quick, _one(root, "updateInstall"))
    assert download.asked == [UPDATE]
    assert _text(root, "updateStatus") == "Downloading…"
    assert _one(root, "updateInstall").property("enabled") is False
    window._on_update_progress(50, 200)
    pump(qapp, 10)
    assert _sheets(window).property("form")["progress"] == 0.25
    assert _one(root, "updateProgress").property("visible") is True
    window._on_update_problem("Could not download the update.")
    pump(qapp, 10)
    assert _text(root, "updateStatus") == "Could not download the update."
    assert _one(root, "updateInstall").property("enabled") is True
    assert _one(root, "updateProgress").property("visible") is False


def test_not_now_and_esc_close_the_update_and_remember_nothing(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    download = _update_rig(window, monkeypatch)
    root, quick = _material(qapp, window)
    window._update_asked = True
    window._on_update_found(UPDATE)
    pump(qapp, 40)
    _click(quick, _one(root, "updateLater"))
    assert _sheets(window).property("kind") == ""
    window._on_update_found(UPDATE)
    pump(qapp, 40)
    _press(quick, Qt.Key.Key_Escape)
    assert _sheets(window).property("kind") == ""
    assert "skip" not in window._updates and download.asked == []


def test_skip_this_version_is_remembered_and_the_sheet_closes(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _update_rig(window, monkeypatch)
    root, quick = _material(qapp, window)
    window._update_asked = True
    window._on_update_found(UPDATE)
    pump(qapp, 40)
    _click(quick, _one(root, "updateSkip"))
    assert _sheets(window).property("kind") == ""
    assert window._updates["skip"] == "1.5.0"
    # A check nobody asked for stays quiet about the skipped version.
    window._update_asked = False
    window._on_update_found(UPDATE)
    pump(qapp, 20)
    assert _sheets(window).property("kind") == ""


def test_a_verified_download_closes_the_sheet_and_quits_for_the_new_version(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _update_rig(window, monkeypatch)
    quit_calls: list[int] = []
    monkeypatch.setattr(window, "quit_app", lambda: quit_calls.append(1))
    monkeypatch.setattr("desktop.native.window.UPDATE_QUIT_MS", 0)
    monkeypatch.setattr("desktop.native.window.apply_update", lambda _path: None)
    root, quick = _material(qapp, window)
    window._update_asked = True
    window._on_update_found(UPDATE)
    pump(qapp, 40)
    window._on_update_ready("/nowhere/FlexWeek")
    pump(qapp, 20)
    assert _sheets(window).property("kind") == ""
    QTest.qWait(30)
    assert quit_calls == [1]


def test_an_update_that_cannot_be_put_in_place_says_so_on_the_sheet(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _update_rig(window, monkeypatch)
    monkeypatch.setattr("desktop.native.window.apply_update", lambda _path: "It did not fit.")
    root, quick = _material(qapp, window)
    window._update_asked = True
    window._on_update_found(UPDATE)
    pump(qapp, 40)
    window._on_update_ready("/nowhere/FlexWeek")
    pump(qapp, 20)
    assert _sheets(window).property("kind") == "update"
    assert _text(root, "updateStatus") == "It did not fit. Open the release page to update by hand."


def test_an_update_waits_for_an_open_sheet_so_typing_is_not_lost(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _update_rig(window, monkeypatch)
    root, quick = _material(qapp, window)
    sheets = _sheets(window)
    sheets.openHomework()
    sheets.setText("title", "History essay")
    pump(qapp, 40)
    window._update_asked = True
    window._on_update_found(UPDATE)
    pump(qapp, 20)
    assert sheets.property("kind") == "homework"
    sheets.forceClose()
    pump(qapp, 20)
    assert sheets.property("kind") == "update"




# Sign out


def _sign_out_rig(window: NativeWindow, monkeypatch: pytest.MonkeyPatch) -> list[int]:
    window.session.storage_info = {"mode": "local"}
    out: list[int] = []
    monkeypatch.setattr(window.session, "logout", lambda: out.append(1))
    return out


def test_sign_out_asks_in_a_material_prompt_with_the_same_words(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _sign_out_rig(window, monkeypatch)
    root, quick = _material(qapp, window)
    _sheets(window).moreAction("signOut")
    pump(qapp, 40)
    ask = dict(_sheets(window).property("ask"))
    assert ask["title"] == "Sign out"
    assert ask["body"] == "Your week is saved on this computer, under this account. Sign in again to see it."
    assert ask["body"] == SIGN_OUT_QUESTION.format(where="this computer")
    assert [(a["label"]) for a in ask["answers"]] == ["Cancel", "Sign out"]
    assert _text(root, "sheetTitle") == "Sign out"
    assert _focused(window) == "prompt_stay", "Cancel is the default, so Enter by habit changes nothing"


def test_sign_out_says_in_full_where_the_week_lives(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    _sign_out_rig(window, monkeypatch)
    _material(qapp, window)
    window._log_out()
    pump(qapp, 20)
    assert dict(_sheets(window).property("ask"))["body"] == (
        "Your week is saved on this computer, under this account. Sign in again to see it."
    )


def test_answering_sign_out_signs_out_once(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _sign_out_rig(window, monkeypatch)
    root, quick = _material(qapp, window)
    window._log_out()
    pump(qapp, 40)
    _click(quick, _one(root, "prompt_yes"))
    assert out == [1]
    assert dict(_sheets(window).property("ask")) == {}


def test_cancel_and_esc_keep_the_student_signed_in_and_the_keyboard_goes_back(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _sign_out_rig(window, monkeypatch)
    root, quick = _material(qapp, window)
    fab = _one(root, "materialFab")
    fab.forceActiveFocus()
    pump(qapp)
    window._log_out()
    pump(qapp, 40)
    _click(quick, _one(root, "prompt_stay"))
    assert dict(_sheets(window).property("ask")) == {}
    window._log_out()
    pump(qapp, 40)
    _press(quick, Qt.Key.Key_Escape)
    assert dict(_sheets(window).property("ask")) == {}
    assert out == []
    assert quick_window_of(window).activeFocusItem() is fab




def test_the_about_logo_sits_on_a_rounded_tile_so_no_white_square_shows_in_dark(
    qapp: QApplication, window: NativeWindow
) -> None:
    root, _quick = _material(qapp, window)
    _sheets(window).openAbout()
    pump(qapp, 40)
    tile = named(root, "aboutLogoTile")[0]
    logo = named(root, "aboutLogo")[0]
    assert float(tile.property("radius")) >= 12
    # The logo's square corner must lie inside the tile's curve: its inset is at least r * (1 - 1/sqrt 2).
    inset = (float(tile.property("width")) - float(logo.property("width"))) / 2
    assert inset >= float(tile.property("radius")) * 0.2929


def test_in_dark_the_page_behind_a_sheet_is_dimmed_harder_and_the_card_has_an_edge(
    qapp: QApplication, window: NativeWindow
) -> None:
    scrims = {}
    for mode in ("light", "dark"):
        look_file().write_text(json.dumps({"material": {"mode": mode}}))
        root, _quick = _material(qapp, window)
        window._material_page.publish()
        _sheets(window).openAbout()
        pump(qapp, 40)
        scrims[mode] = (
            float(named(root, "sheetScrim")[0].property("opacity")),
            float(QQmlProperty(named(root, "sheetCard")[0], "border.width").read()),
        )
        _sheets(window).closeSheet()
        pump(qapp, 10)
    assert scrims["light"] == (0.32, 0.0)
    assert scrims["dark"] == (0.6, 1.0)
