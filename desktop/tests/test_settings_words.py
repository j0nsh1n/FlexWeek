"""Settings in the words a student looks for, in the order they look (0.15 rows 15, 18, 19, 29).

Appearance & layout opened on an implementation note, then Animations, then a box inside a box with
the style rows in a grey table. The version said 0.14.3. Account and Availability sat together
under This computer, and "Long break after 4" did not say four of what.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QWidget,
)

from desktop.native.settings import PrefsDialog
from desktop.native.update import WINDOWS_SETUP, available
from desktop.native.version import VERSION
from desktop.native.window import NativeWindow
from desktop.tests.window_support import qapp, server, signed_out, window  # noqa: F401


def prefs(window: NativeWindow, layout: dict | None = None) -> PrefsDialog:  # noqa: F811
    session = window.session
    dialog = PrefsDialog(
        window, session.preferences, window._look, session.reminder_limits, layout or window._layout
    )
    dialog.show()
    QApplication.processEvents()
    return dialog


def page(dialog: PrefsDialog, row: int) -> QWidget:
    return dialog.stack.widget(row).widget()


def label_for(widget: QWidget) -> str:
    form = widget.parentWidget().layout()
    assert isinstance(form, QFormLayout)
    label = form.labelForField(widget)
    return label.text() if isinstance(label, QLabel) else ""


def top(widget: QWidget, within: QWidget) -> int:
    return widget.mapTo(within, widget.rect().topLeft()).y()


def test_this_build_says_0_15_0_and_is_not_offered_0_14_3(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    assert VERSION == "0.15.0"
    release = {
        "tag_name": "v0.14.3",
        "assets": [
            {"name": name, "browser_download_url": f"https://example.invalid/{name}"}
            for name in (WINDOWS_SETUP, WINDOWS_SETUP + ".sha256")
        ],
    }
    assert available(release, "windows") is None
    assert available({**release, "tag_name": "v0.15.1"}, "windows")["version"] == "0.15.1"
    dialog = prefs(window)
    assert dialog.findChild(QLabel, "prefsVersion").text() == "FlexWeek 0.15.0"
    dialog.close()


def test_appearance_opens_on_main_view_and_ends_with_animations_and_fine_tune(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    dialog = prefs(window, {"main": "timeline", "day": "one", "options": {}})
    appearance = page(dialog, 0)
    assert appearance.findChildren(QGroupBox) == [], "no box inside the page's box"
    shown = sorted(
        (label for label in appearance.findChildren(QLabel) if label.isVisibleTo(dialog) and label.text()),
        key=lambda label: top(label, appearance),
    )
    assert [label.text() for label in shown[:2]] == [
        "MAIN VIEW",
        "A design is how FlexWeek lays out your week. Your blocks and homework are the same in every one.",
    ]
    assert not any("has its own colours" in label.text() for label in shown)
    order = [
        appearance.findChild(QComboBox, "layoutMain"),
        appearance.findChild(QComboBox, "layoutMain-colour"),
        appearance.findChild(QComboBox, "layoutDay"),
        dialog.motion,
        dialog.fine_tune,
    ]
    tops = [top(widget, appearance) for widget in order]
    assert tops == sorted(tops), tops
    # What the note said, where it applies: under the colours it is about.
    colour = appearance.findChild(QComboBox, "layoutMain-colour")
    note = appearance.findChild(QLabel, "layoutMainColourNote")
    assert note.text() == "Pick Match my look to use your own Look and Accent."
    assert note.isVisibleTo(dialog)
    assert 0 < top(note, appearance) - top(colour, appearance) < 3 * colour.height()
    colour.setCurrentIndex(colour.findData("match"))
    qapp.processEvents()
    assert not note.isVisibleTo(dialog)
    dialog.close()


def test_the_style_rows_sit_on_the_page_not_in_a_grey_table(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    dialog = prefs(window, {"main": "timeline", "day": "one", "options": {}})
    appearance = page(dialog, 0)
    colour = appearance.findChild(QComboBox, "layoutMain-colour")
    heading = appearance.findChild(QLabel, "layoutMainHeading")
    picture = appearance.grab().toImage()
    beside_colour = picture.pixelColor(2, top(colour, appearance) + colour.height() // 2)
    beside_heading = picture.pixelColor(2, top(heading, appearance) + heading.height() // 2)
    assert beside_colour == beside_heading, "the style rows are painted on a band of their own"
    dialog.close()


def test_focus_says_what_the_long_break_counts(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    dialog = prefs(window)
    assert label_for(dialog.long_every) == "Long break after"
    assert dialog.long_every.text() == "4 focus sessions"
    assert label_for(dialog.long_break) == "Long break minutes"
    dialog.close()


def test_account_has_its_own_row_and_availability_is_under_planning(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    dialog = prefs(window)
    account = dialog.findChild(QPushButton, "prefsAccount")
    availability = dialog.findChild(QPushButton, "prefsAvailability")
    assert account.text() == "Manage account…"
    assert label_for(account) == "Account"
    assert page(dialog, 4).isAncestorOf(account)
    assert availability.text() == "Availability…"
    assert page(dialog, 1).isAncestorOf(availability), "Availability is about when to plan"
    asked: list[str] = []
    dialog.availability_requested.connect(lambda: asked.append("availability"))
    availability.click()
    assert asked == ["availability"]
    dialog.close()


def test_a_sound_test_that_hears_nothing_says_what_to_do(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dialog = prefs(window)
    monkeypatch.setattr(dialog._bell, "once", lambda _tone, _volume: False)
    dialog.reminder_sound.setChecked(True)
    dialog.volume.setValue(80)
    dialog.preview.click()
    assert dialog.preview.text() == "Test"
    assert dialog.save_state.text() == (
        "No sound came out. Check that speakers or headphones are plugged in and not muted, then "
        "press Test again. Alerts still appear on screen."
    )
    dialog.volume.setValue(0)
    dialog.preview.click()
    assert dialog.save_state.text() == (
        "Alert volume is 0, so there is nothing to hear. Turn it up, then press Test."
    )
    dialog.close()


def test_fine_tune_is_the_last_thing_on_appearance(
    qapp: QApplication,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    dialog = prefs(window)
    appearance = page(dialog, 0)
    boxes = [box for box in appearance.findChildren(QCheckBox) if box.isVisibleTo(dialog)]
    assert max(boxes, key=lambda box: top(box, appearance)) is dialog.fine_tune
    dialog.close()
