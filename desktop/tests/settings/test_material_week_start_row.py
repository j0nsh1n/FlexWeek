"""Material 3 Settings > Planning leads with "Your week": the day the week starts on, any of the
seven, in a drop-down list from Monday to Sunday. It is the same per-computer setting Widgets Settings
and both Setups change, so a pick here is what Widgets Settings shows."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QComboBox

from desktop.native import fields
from desktop.native.settings import SettingsPage
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.settings.support_material_settings import _named, _open_settings, _panel, _texts
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

# ruff: noqa: F811

SEVEN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _widgets_choice(window: NativeWindow) -> str:
    page = SettingsPage(
        window, window.session.preferences or {}, window._look, window.session.reminder_limits
    )
    try:
        return page.findChild(QComboBox, "prefWeekStart").currentText()
    finally:
        page.deleteLater()


def test_planning_starts_with_the_week_start_day_out_of_all_seven(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window, "planning")
    rows = [item for item in _named(root, "row_weekStart") if item.property("visible")]
    assert len(rows) == 1
    words = [str(item.property("text")) for item in _texts(rows[0])]
    assert "Week starts on" in words
    # The words of the picked settings mockup: Week follows the day too.
    assert "Week, Month and the date pickers start on this day." in words
    headers = [item for item in _named(root, "header_your week") if item.property("visible")]
    assert len(headers) == 1
    assert "Your week" in [str(item.property("text")) for item in _texts(headers[0])]
    choice = _named(root, "weekStart")[0]
    assert [row["label"] for row in choice.property("options").toVariant()] == SEVEN
    assert choice.property("value") == "monday"
    assert choice.property("accessName") == "Week starts on"


def test_a_day_picked_in_material_settings_is_kept_on_this_computer_and_shown_by_widgets(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window, "planning")
    _panel(window).setWeekStart("wednesday")
    assert fields.week_starts_on() == "wednesday"
    wait_until(qapp, lambda: _named(root, "weekStart")[0].property("value") == "wednesday")
    assert _widgets_choice(window) == "Wednesday"
    _panel(window).setWeekStart("someday")
    assert fields.week_starts_on() == "wednesday"
