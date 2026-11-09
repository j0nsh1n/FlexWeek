# ruff: noqa: F811
"""The week page's top bar: which buttons it keeps in every design, that none is offered twice, and what
the Add button says about a drag."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QAbstractButton, QApplication, QPushButton  # noqa: E402

from desktop.native.layouts.registry import LAYOUTS  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    click,
    qapp,  # noqa: F401
    window,  # noqa: F401
)


def test_every_main_view_has_add_on_the_top_bar(qapp: QApplication, window: NativeWindow) -> None:
    """Add is the top bar's in every design; a design draws no second one."""
    for spec in LAYOUTS.values():
        if spec.role != "plan":
            continue
        window._layout = {"main": spec.id, "day": "one", "options": {}}
        window._on_week()
        qapp.processEvents()
        assert window.findChild(QPushButton, "addButton").isVisible(), spec.id


def test_bentos_buttons_reach_the_products_own_add_and_plan(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bento draws no Add of its own: the top bar's is the one it uses."""
    asked: list[str] = []
    monkeypatch.setattr(NativeWindow, "_add_homework", lambda self: asked.append("add"))
    monkeypatch.setattr(type(window.session), "solve", lambda self: asked.append("plan"))
    window._layout = {"main": "bento", "day": "one", "options": {}}
    window._on_week()
    assert window.planner.currentWidget().findChild(QPushButton, "bentoAdd") is None
    click(window, "addButton")
    click(window, "solveButton")
    click(window, "viewMyDay")
    assert asked == ["add", "plan"]
    assert type(window.planner.currentWidget()).__name__ == "OneThingView"


def test_the_week_toolbar_keeps_only_what_is_reached_for(qapp: QApplication, window: NativeWindow) -> None:
    """The row keeps adding, planning, saving and starting a timer; everything else sits under the
    heading for its job in More. Retry save is not here: it appears only when a save has failed."""
    page = window._stack.currentWidget()
    shown = [
        button.objectName()
        for button in page.findChildren(QAbstractButton)
        # The calendar's own controls, such as zooming its hours or paging the rail's month, belong to
        # it, not to the toolbar.
        if button.isVisible()
        and button.objectName()
        and not window.planner.isAncestorOf(button)
        and not window.rail.isAncestorOf(button)
    ]
    assert window.findChild(QPushButton, "weekZoomIn").isVisible()
    assert shown == [
        "prevWeek",
        "nextWeek",
        "todayWeek",
        "weekTitleMark",
        "viewDay",
        "viewWeek",
        "viewMonth",
        "viewMyDay",
        "addButton",
        "addArrow",
        "solveButton",
        "moreButton",
        "settingsGear",
    ]


def test_no_button_appears_twice_on_the_week_page(qapp: QApplication, window: NativeWindow) -> None:
    """Moving Quick focus into the action row left the focus panel's own copy on screen, so the same
    button was offered twice. The action row is not the only place a button can come from, so this counts
    them across the whole page rather than inside one container."""
    window._day_mode = False
    window._on_week()
    qapp.processEvents()
    page = window._stack.currentWidget()
    labels = [b.text() for b in page.findChildren(QPushButton) if b.isVisible() and b.text()]
    repeated = sorted({text for text in labels if labels.count(text) > 1})
    assert repeated == [], f"offered twice: {repeated}"


def test_the_add_button_says_what_a_drag_will_make(qapp: QApplication, window: NativeWindow) -> None:
    """With the category chips gone, the button that opens the menu has to carry the armed type."""
    # arm_category, not _add_from_chip: that one also opens the Add dialog, which blocks.
    window.session.arm_category("exercise")
    window._sync_add_button()
    qapp.processEvents()
    button = window.findChild(QPushButton, "addButton")
    assert button is not None
    assert "sport" in button.text().lower()
    assert not button.icon().isNull(), "no colour beside the armed type"
