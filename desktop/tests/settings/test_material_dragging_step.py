"""Material 3 Settings > Planning: the time step the student drags and picks times in, 5 or 15 minutes.
It is the same account preference Widgets Settings and both Setups set, so a pick here shows there."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QRadioButton

from desktop.native.settings import SettingsPage
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.settings.support_material_settings import (
    _click_segment,
    _named,
    _open_settings,
    _panel,
    _prefs,
    _texts,
)
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

# ruff: noqa: F811


def _widgets_choice(window: NativeWindow) -> int:
    """The step Widgets Settings shows as chosen, read from the saved preferences."""
    page = SettingsPage(
        window, window.session.preferences or {}, window._look, window.session.reminder_limits
    )
    try:
        return next(
            minutes
            for minutes in (5, 15)
            if page.findChild(QRadioButton, f"prefDragStep-{minutes}").isChecked()
        )
    finally:
        page.deleteLater()


def test_planning_offers_a_dragging_step_of_5_or_15_minutes_marked_as_saved(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window, "planning")
    rows = [item for item in _named(root, "row_dragStep") if item.property("visible")]
    assert len(rows) == 1
    words = [str(item.property("text")) for item in _texts(rows[0])]
    assert "Dragging step" in words
    assert "How far blocks move when you drag them and the times offered in lists." in words
    assert words.count("5 min") == 1
    assert words.count("15 min") == 1
    # An account that never chose drags in fives.
    assert _named(root, "dragStep")[0].property("current") == "5"

    window.session.preferences["drag_step_min"] = 15
    _panel(window)._publish()
    wait_until(qapp, lambda: _named(root, "dragStep")[0].property("current") == "15")


def test_a_step_picked_in_material_settings_is_saved_and_shown_by_widgets_settings(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window, "planning")
    _click_segment(qapp, window, _named(root, "dragStep")[0], "15 min")
    wait_until(qapp, lambda: _prefs(window).get("drag_step_min") == 15)
    wait_until(qapp, lambda: _named(root, "dragStep")[0].property("current") == "15")
    assert _widgets_choice(window) == 15
    assert window.hand.step == 15

    _click_segment(qapp, window, _named(root, "dragStep")[0], "5 min")
    wait_until(qapp, lambda: _prefs(window).get("drag_step_min", 5) == 5)
    wait_until(qapp, lambda: _named(root, "dragStep")[0].property("current") == "5")
    assert _widgets_choice(window) == 5
    assert window.hand.step == 5
