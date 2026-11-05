"""Tests for PR 8: Material segmented choice follows its value after a click (audit P1-2).

Verifies:
- test_a_typed_length_moves_the_tick_off_a_clicked_chip: click "45 min", type 37 -> no chip ticked;
  type 60 -> only "60 min" ticked; type 0 -> none ticked.
- test_arrow_keys_still_move_the_choice_and_the_estimate: focus the Quick lengths row,
  press Right twice from 15 min -> estimate is 45 and "45 min" is ticked.
- test_a_settings_choice_follows_its_setting_after_a_click: click one option,
  change setting from Python -> tick follows.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

pytest_plugins = ["desktop.tests.test_material_sheets"]

from PySide6.QtCore import QObject, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.test_layouts_window import look_file, wait_until  # noqa: E402
from desktop.tests.test_material_sheets import (  # noqa: E402
    _find,
    _type_homework,
)
from desktop.tests.test_material_window import (  # noqa: E402
    _named,
    _pump,
    _show_material,
    _visuals,
)


def _texts(item: QObject) -> list[QObject]:
    found: list[QObject] = []
    for child in item.childItems():
        if child.property("text") is not None and child.property("font") is not None:
            found.append(child)
        found.extend(_texts(child))
    return found


def _click(quick: QObject, item: QObject, qapp: QApplication) -> None:
    centre = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
    QTest.mouseClick(
        quick,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        centre,
    )
    _pump(qapp, 10)


def _click_segment(qapp: QApplication, shell: NativeWindow, seg: QObject, label: str) -> None:
    quick = shell._material_page._quick
    for item in _texts(seg):
        if str(item.property("text")) == label:
            _click(quick, item, qapp)
            return
    raise AssertionError(f"no segment {label!r}")


def _ticked_labels(segmented: QObject) -> list[str]:
    shape = _named(segmented, "shape")[0]
    row = shape.childItems()[0]
    ticked: list[str] = []
    for d in row.childItems():
        if d.property("on"):
            caps = [c for c in _visuals(d) if c.property("text") is not None]
            if caps:
                ticked.append(str(caps[0].property("text")))
    return ticked


def _go_to_step_3(qapp: QApplication, shell: NativeWindow, sheets) -> QObject:
    root = _show_material(qapp, shell)
    sheets.openHomework()
    _type_homework(sheets, "History essay")
    sheets.next()
    sheets.next()
    _pump(qapp, 10)
    assert sheets.form["step"] == 2
    return root


def test_a_typed_length_moves_the_tick_off_a_clicked_chip(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    root = _go_to_step_3(qapp, shell, sheets)
    quick_btn = _find(root, "homeworkQuick")
    assert quick_btn is not None

    # Initial state at step 3: default is 60 min
    assert quick_btn.property("current") == "60"
    assert _ticked_labels(quick_btn) == ["60 min"]

    # Click "45 min" chip
    _click_segment(qapp, shell, quick_btn, "45 min")
    _pump(qapp, 10)
    assert sheets.form["estimate"] == "45"
    assert quick_btn.property("current") == "45"
    assert _ticked_labels(quick_btn) == ["45 min"]

    # Type 37 -> no chip ticked
    sheets.setText("estimate", "37")
    _pump(qapp, 10)
    assert sheets.form["estimate"] == "37"
    assert quick_btn.property("current") == "37"
    assert _ticked_labels(quick_btn) == []

    # Type 60 -> only "60 min" ticked
    sheets.setText("estimate", "60")
    _pump(qapp, 10)
    assert sheets.form["estimate"] == "60"
    assert quick_btn.property("current") == "60"
    assert _ticked_labels(quick_btn) == ["60 min"]

    # Type 0 -> none ticked
    sheets.setText("estimate", "0")
    _pump(qapp, 10)
    assert sheets.form["estimate"] == "0"
    assert quick_btn.property("current") == "0"
    assert _ticked_labels(quick_btn) == []


def test_arrow_keys_still_move_the_choice_and_the_estimate(
    qapp: QApplication, shell: NativeWindow, sheets
) -> None:
    root = _go_to_step_3(qapp, shell, sheets)
    quick_btn = _find(root, "homeworkQuick")
    assert quick_btn is not None

    # Start from 15 min
    _click_segment(qapp, shell, quick_btn, "15 min")
    _pump(qapp, 10)
    assert sheets.form["estimate"] == "15"
    assert quick_btn.property("current") == "15"
    assert _ticked_labels(quick_btn) == ["15 min"]

    # Focus the Quick lengths row
    quick = shell._material_page._quick
    quick_btn.forceActiveFocus()
    _pump(qapp, 5)
    assert quick_btn.property("activeFocus") is True

    # Press Right once -> moves to 30 min
    QTest.keyClick(quick, Qt.Key.Key_Right)
    _pump(qapp, 10)
    assert sheets.form["estimate"] == "30"
    assert quick_btn.property("current") == "30"
    assert _ticked_labels(quick_btn) == ["30 min"]

    # Press Right second time -> moves to 45 min
    QTest.keyClick(quick, Qt.Key.Key_Right)
    _pump(qapp, 10)
    assert sheets.form["estimate"] == "45"
    assert quick_btn.property("current") == "45"
    assert _ticked_labels(quick_btn) == ["45 min"]


def test_a_settings_choice_follows_its_setting_after_a_click(qapp: QApplication, shell: NativeWindow) -> None:
    root = _show_material(qapp, shell)
    bridge = shell._material_page.bridge
    panel = bridge._settings_bridge
    try:
        bridge.showPage("settings")
        panel.openAdvanced()
        _pump(qapp, 10)

        preview_fit = _find(root, "previewFit")
        assert preview_fit is not None
        assert preview_fit.property("current") == "Fit"
        assert _ticked_labels(preview_fit) == ["Fit"]

        # Click "Actual size"
        _click_segment(qapp, shell, preview_fit, "Actual size")
        wait_until(qapp, lambda: panel.property("state")["previewFit"] == "Actual")
        assert preview_fit.property("current") == "Actual"
        assert _ticked_labels(preview_fit) == ["Actual size"]

        # Change setting from Python -> tick follows
        panel.setPreviewFit("Fit")
        wait_until(qapp, lambda: panel.property("state")["previewFit"] == "Fit")
        _pump(qapp, 10)
        assert preview_fit.property("current") == "Fit"
        assert _ticked_labels(preview_fit) == ["Fit"]
    finally:
        panel.closeAdvanced()
        look_file().unlink(missing_ok=True)
        bridge.reload_material()
        panel.note_applied()
        shell._use_widgets_styles()


def test_arrow_keys_step_on_while_a_settings_save_is_still_on_its_way(
    qapp: QApplication, shell: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reminders are saved on the server, so the answer comes later. Two Right presses from Off before it
    comes must ask for 5 and then 10 minutes, with the tick on 10m; a failed answer puts back the saved
    one."""
    session = shell.session
    session.save_preferences({"reminders_enabled": False})
    wait_until(qapp, lambda: (session.preferences or {}).get("reminders_enabled") is False)
    held: list[tuple[dict, object]] = []

    def hold(updates: dict, then=None) -> bool:
        held.append((dict(updates), then))
        return True

    monkeypatch.setattr(session, "save_preferences", hold)
    root = _show_material(qapp, shell)
    bridge = shell._material_page.bridge
    panel = bridge._settings_bridge
    try:
        bridge.showPage("settings")
        panel.closeAdvanced()
        panel.setSection("alerts")
        _pump(qapp, 10)
        reminder = _named(root, "reminder")[0]
        assert _ticked_labels(reminder) == ["Off"]
        reminder.forceActiveFocus()
        _pump(qapp, 5)
        quick = shell._material_page._quick
        QTest.keyClick(quick, Qt.Key.Key_Right)
        _pump(qapp, 10)
        QTest.keyClick(quick, Qt.Key.Key_Right)
        _pump(qapp, 10)

        assert [updates.get("reminder_lead_min") for updates, _then in held] == [5, 10]
        assert all(updates.get("reminders_enabled") is True for updates, _then in held)
        assert _ticked_labels(reminder) == ["10m"]

        held[-1][1](False)
        _pump(qapp, 10)
        assert _ticked_labels(reminder) == ["Off"]
    finally:
        monkeypatch.undo()
        panel.closeAdvanced()
        look_file().unlink(missing_ok=True)
        bridge.reload_material()
        panel.note_applied()
        shell._use_widgets_styles()
