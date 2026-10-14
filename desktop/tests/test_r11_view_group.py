"""R11: the four planner views act as one accessible radio group."""

# ruff: noqa: F811  (pytest fixtures imported by name)
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAccessible, QFontMetrics
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QRadioButton, QStyle, QStyleOptionButton

from desktop.native.fonts import weighted
from desktop.native.layouts.registry import LAYOUTS
from desktop.native.look import LOOK_PRESETS, VIEW_BUTTONS
from desktop.native.tokens import WEIGHT_REGULAR, WEIGHT_STRONG
from desktop.native.widgets import SegmentTrack
from desktop.tests.window_support import qapp, server, signed_out, window  # noqa: F401


def views(window) -> list[QRadioButton]:
    return [window.findChild(QRadioButton, name) for name in VIEW_BUTTONS]


def press(window, key) -> None:
    QTest.keyClick(window.windowHandle(), key)
    QApplication.processEvents()


def selected(buttons: list[QRadioButton]) -> int:
    return next(index for index, button in enumerate(buttons) if button.isChecked())


def test_view_switcher_is_one_keyboard_radio_group(qapp, window) -> None:
    buttons = views(window)
    group = window.findChild(SegmentTrack, "segments")
    assert group is not None
    buttons[1].click()
    qapp.processEvents()
    assert [button for button in buttons if button.focusPolicy() & Qt.FocusPolicy.TabFocus] == [buttons[1]]

    before = buttons[0].previousInFocusChain()
    while before is not None and (
        before in buttons
        or not (before.isVisible() and before.focusPolicy() & Qt.FocusPolicy.TabFocus)
    ):
        before = before.previousInFocusChain()
    assert before is not None
    before.setFocus(Qt.FocusReason.OtherFocusReason)
    press(window, Qt.Key.Key_Tab)
    assert QApplication.focusWidget() is buttons[selected(buttons)]

    for key, expected in (
        (Qt.Key.Key_Left, 0),
        (Qt.Key.Key_Right, 1),
        (Qt.Key.Key_Up, 0),
        (Qt.Key.Key_Down, 1),
        (Qt.Key.Key_Home, 0),
        (Qt.Key.Key_End, 3),
    ):
        press(window, key)
        assert selected(buttons) == expected
        assert QApplication.focusWidget() is buttons[expected]
        assert bool(window._day_mode) is (expected == 3)


def test_view_switcher_has_radio_roles_and_one_accessible_group(qapp, window) -> None:
    buttons = views(window)
    group = window.findChild(SegmentTrack, "segments")
    group_face = QAccessible.queryAccessibleInterface(group)
    assert group_face.role() == QAccessible.Role.Grouping
    assert group_face.text(QAccessible.Text.Name) == "Planner view"
    chosen = selected(buttons)
    for index, button in enumerate(buttons):
        face = QAccessible.queryAccessibleInterface(button)
        assert face.role() == QAccessible.Role.RadioButton
        assert bool(face.state().checked) is (index == chosen)
        assert face.text(QAccessible.Text.Name) == button.text()
        assert face.text(QAccessible.Text.Description) == f"{index + 1} of 4"
        assert face.parent().object() is group


def test_view_labels_fit_and_targets_stay_large_enough(qapp, window) -> None:
    for design in LAYOUTS:
        for preset in LOOK_PRESETS:
            for size in ("small", "normal", "large"):
                _check_view_labels(qapp, window, design, preset, size)


def _check_view_labels(qapp, window, design, preset, size) -> None:
    window.resize(1280, 860)
    window._layout = {"main": design, "day": "one", "options": {}}
    window._look = {"preset": preset, "knobs": {"text": size}}
    window.session.look = window._look
    window._apply_appearance()
    qapp.processEvents()

    for button in views(window):
        option = QStyleOptionButton()
        button.initStyleOption(option)
        contents = button.style().subElementRect(
            QStyle.SubElement.SE_PushButtonContents, option, button
        )
        font = weighted(button.font(), WEIGHT_STRONG if button.isChecked() else WEIGHT_REGULAR)
        needed = QFontMetrics(font).horizontalAdvance(button.text())
        assert contents.width() >= needed, f"{design}/{preset}/{size}: {button.text()} clips"
        assert button.width() >= 24 and button.height() >= 24, (
            f"{design}/{preset}/{size}: {button.text()} is {button.width()}x{button.height()}"
        )


def test_view_buttons_have_equal_padding_at_large_text(qapp, window) -> None:
    for design in LAYOUTS:
        for preset in LOOK_PRESETS:
            _check_equal_padding(qapp, window, design, preset)


def _check_equal_padding(qapp, window, design, preset) -> None:
    window.resize(1280, 860)
    window._layout = {"main": design, "day": "one", "options": {}}
    window._look = {"preset": preset, "knobs": {"text": "large"}}
    window.session.look = window._look
    window._apply_appearance()
    qapp.processEvents()

    gaps = [
        button.width()
        - QFontMetrics(
            weighted(button.font(), WEIGHT_STRONG if button.isChecked() else WEIGHT_REGULAR)
        ).horizontalAdvance(button.text())
        for button in views(window)
    ]
    assert len(set(gaps)) == 1, f"{design}/{preset}: padding gaps differ: {gaps}"
