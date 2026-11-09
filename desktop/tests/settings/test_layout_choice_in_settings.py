# ruff: noqa: F811
"""The Main view and Day screen choices in Settings: their names, what each level shows, what is stored,
and how a design's own options come and go."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QCheckBox, QPushButton  # noqa: E402

from desktop.native.layouts.registry import LAYOUTS  # noqa: E402
from desktop.native.layouts.views import VIEW_CLASSES  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    combo,
    prefs_layout,
    qapp,  # noqa: F401
    rows,
)


def test_every_view_has_one_name(qapp: QApplication) -> None:
    """ "Calendar · Today's app" was two names for one design; the card's words under the name say what
    it is for."""
    dialog = prefs_layout()
    main = combo(dialog, "layoutMain")
    assert [main.itemText(index) for index in range(main.count())] == [
        "Today's app",
        "Timeline",
        "Mission control",
        "Bento",
        "Retro desktop",
        "Clay deck",
    ]


def test_settings_shows_only_what_the_main_view_uses(qapp: QApplication) -> None:
    """Surface, Corners and Blocks stayed on screen for every design, though only Today's app reads
    them, so a student changed them in Bento and nothing happened. Look and Accent stay for every
    design: they dress the top bar and every window whatever the design."""
    from desktop.native.settings import FINE_TUNE_LOOK, TODAYS_APP_KNOBS

    dialog = prefs_layout({"main": "classic", "day": "one", "options": {}})
    dialog.fine_tune.setChecked(True)
    dialog.show()
    qapp.processEvents()

    def shown() -> dict[str, bool]:
        fields = {"look": dialog.look, "accent": dialog.accent, "chips": dialog.accent_chips}
        fields.update(dialog.knobs)
        return {name: field.isVisibleTo(dialog) for name, field in fields.items()}

    everything = shown()
    assert all(everything.values())
    assert dialog.fine_tune.text() == FINE_TUNE_LOOK

    main = combo(dialog, "layoutMain")
    main.setCurrentIndex(main.findData("bento"))
    qapp.processEvents()
    matched = shown()
    assert {name for name, on in matched.items() if not on} == set(TODAYS_APP_KNOBS) - {"surface"}
    assert dialog.fine_tune.text() == FINE_TUNE_LOOK

    colour = combo(dialog, "layoutMain-look")
    colour.setCurrentIndex(colour.findData("preset:high-contrast"))
    qapp.processEvents()
    own = shown()
    assert {name for name, on in own.items() if not on} == set(TODAYS_APP_KNOBS) - {"surface"}
    assert dialog.fine_tune.text() == FINE_TUNE_LOOK

    main.setCurrentIndex(main.findData("classic"))
    qapp.processEvents()
    assert all(shown().values())
    dialog.close()


def test_the_dialog_shows_style_first_and_fine_tune_on_request(qapp: QApplication) -> None:
    dialog = prefs_layout()
    assert [combo(dialog, "layoutDay").itemText(index) for index in range(2)] == [
        "Day dial",
        "One thing",
    ]
    pick = combo(dialog, "layoutDay")
    pick.setCurrentIndex(pick.findData("one"))
    assert rows(dialog, "Day") == ["layoutDay-look"]
    dialog.findChild(QCheckBox, "layoutDayMore").setChecked(True)
    assert rows(dialog, "Day") == [
        "layoutDay-actions",
        "layoutDay-daybar",
        "layoutDay-lead",
        "layoutDay-look",
    ]
    assert rows(dialog, "Main") == ["layoutMain-look"]


def test_the_dialog_stores_only_what_the_student_changed(qapp: QApplication) -> None:
    dialog = prefs_layout({"main": "classic", "day": "one"})
    assert dialog.layout_choice() == {"main": "classic", "day": "one", "options": {}}
    colour = combo(dialog, "layoutDay-look")
    colour.setCurrentIndex(colour.findData("preset:one-paper"))
    assert dialog.layout_choice()["options"] == {"one": {"look": "preset:one-paper"}}
    colour = combo(dialog, "layoutDay-look")
    colour.setCurrentIndex(colour.findData("your"))
    assert dialog.layout_choice()["options"] == {}


def test_fine_tuning_already_in_use_is_not_hidden(qapp: QApplication) -> None:
    dialog = prefs_layout({"day": "one", "options": {"one": {"daybar": "hide"}}})
    assert dialog.findChild(QCheckBox, "layoutDayMore").isChecked() is True
    assert combo(dialog, "layoutDay-daybar").currentData() == "hide"


def test_trying_another_design_and_coming_back_loses_nothing(qapp: QApplication) -> None:
    dialog = prefs_layout({"day": "one", "options": {"one": {"look": "preset:one-paper"}}})
    pick = combo(dialog, "layoutDay")
    pick.setCurrentIndex(pick.findData("dial"))
    assert combo(dialog, "layoutDay-look").currentData() == "preset:dial-midnight"
    pick.setCurrentIndex(pick.findData("one"))
    assert combo(dialog, "layoutDay-look").currentData() == "preset:one-paper"
    assert dialog.layout_choice()["options"] == {
        "dial": {"look": "preset:dial-midnight"},
        "one": {"look": "preset:one-paper"},
    }


def test_a_design_can_be_put_back_to_its_own_settings(qapp: QApplication) -> None:
    dialog = prefs_layout({"day": "one", "options": {"one": {"look": "preset:one-paper", "lead": "next"}}})
    dialog.findChild(QPushButton, "layoutDayReset").click()
    assert dialog.layout_choice()["options"] == {}
    assert dialog.findChild(QCheckBox, "layoutDayMore").isChecked() is False
    assert dialog.findChild(QPushButton, "layoutDayReset").text() == "Reset this layout's options"


def test_every_built_view_is_a_design_in_the_registry(qapp: QApplication) -> None:
    # Today's app is the week grid itself, so it is the one design with no view of its own.
    assert set(VIEW_CLASSES) == set(LAYOUTS) - {"classic"}
    assert all(view.layout_id == layout_id for layout_id, view in VIEW_CLASSES.items())


def test_fine_tune_and_reset_show_only_when_a_design_has_something_for_them(qapp: QApplication) -> None:
    """Today's app has nothing to change, Bento only styles, and Timeline also fine-tunes."""
    dialog = prefs_layout()
    dialog.show()
    qapp.processEvents()

    def offered() -> tuple[bool, bool]:
        return (
            dialog.findChild(QCheckBox, "layoutMainMore").isVisible(),
            dialog.findChild(QPushButton, "layoutMainReset").isVisible(),
        )

    assert offered() == (False, False)
    pick = combo(dialog, "layoutMain")
    pick.setCurrentIndex(pick.findData("bento"))
    assert offered() == (False, True)
    pick.setCurrentIndex(pick.findData("timeline"))
    assert offered() == (True, True)
    pick.setCurrentIndex(pick.findData("classic"))
    assert offered() == (False, True)
