"""With Animations at Off nothing moves anywhere. Each main transition is walked and, right after it, no
clock has run, no picture or dim is over the page, and no widget is drawn through a fade."""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Callable, Iterator

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QAbstractButton, QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

    import desktop.native.motion as motion
    from desktop.native.layout_choice import sanitize_layout
    from desktop.native.motion import (
        FADE_NAME,
        SLIDE_NAME,
        Dim,
        Shift,
        app_level,
        apply_ui_effects,
        switch_page,
    )
    from desktop.native.widgets import Dialog, HomeworkDialog, SheetShade
    from desktop.native.window import NativeWindow
    from desktop.tests.light_app import window  # noqa: F401
    from desktop.tests.settings.support_motion import LATER, Hours, pictures, two_pages
    from desktop.tests.test_week_side import seeded
    from desktop.tests.waiting import wait_until
    from desktop.tests.window_support import qapp, settled, still  # noqa: F401


@pytest.fixture(autouse=True)
def motion_is_put_back() -> Iterator[None]:
    apply_ui_effects("normal")
    yield
    apply_ui_effects("normal")


def moving(root: QWidget) -> list[str]:
    """Everything under `root` that is a picture, a dim or a fade. Walks `children()`: findChildren
    would hand a sheet to the window to own."""
    found: list[str] = []
    waiting: list[object] = list(root.children())
    while waiting:
        child = waiting.pop()
        if not isinstance(child, QWidget):
            continue
        waiting.extend(child.children())
        picture = isinstance(child, QLabel) and child.objectName() in (FADE_NAME, SLIDE_NAME)
        if picture and not child.isHidden():
            found.append(f"picture {child.objectName()}")
        if isinstance(child, Dim) and not child.isHidden():
            found.append("dim")
        if isinstance(child, SheetShade) and child.graphicsEffect() is not None:
            found.append("fading backdrop")
        if isinstance(child.graphicsEffect(), Shift):
            found.append(f"fade on {child.objectName() or type(child).__name__}")
    return found


def go_off(qapp: QApplication, window: NativeWindow) -> None:  # noqa: F811
    """The window signed in with a seeded week at Off."""
    # Saved, not set on the session: a later reload of the preferences would put Normal back.
    assert window.session.save_preferences({"motion": "off"})
    settled(qapp, window)
    window._apply_appearance()
    assert window._motion == "off"
    seeded(qapp, window)
    window.resize(1280, 800)
    window.show()
    still(window)
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()


def design(qapp: QApplication, window: NativeWindow, main: str) -> None:  # noqa: F811
    window._layout = sanitize_layout({"main": main})
    window._apply_appearance()
    window.session.set_view("week")
    window._on_week()
    qapp.processEvents()


def press(qapp: QApplication, window: NativeWindow, name: str) -> None:  # noqa: F811
    window.findChild(QAbstractButton, name).click()
    qapp.processEvents()


def test_every_main_transition_at_off_starts_no_clock_and_leaves_nothing_moving(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    go_off(qapp, window)
    starts: list[str] = []
    real_start = motion.Clock.start

    def counted(self: motion.Clock, total: int, step: Callable[[float], None]) -> None:
        starts.append(f"{total} ms on {type(self.parent()).__name__}")
        real_start(self, total, step)

    monkeypatch.setattr(motion.Clock, "start", counted)
    seen: list[tuple[str, list[str]]] = []

    def now() -> list[str]:
        return [*moving(window), *(["a clock is running"] if motion.busy() else [])]

    def check(what: str) -> None:
        seen.append((what, now()))
        qapp.processEvents()
        seen.append((what + ", a turn later", now()))

    for main in ("classic",):
        design(qapp, window, main)
        check(f"{main} chosen")
        for name in ("viewDay", "viewMonth", "viewWeek", "viewWeek"):
            press(qapp, window, name)
            check(f"{main}: {name}")
            if name == "viewMonth":
                wait_until(qapp, lambda: window.session.month_data is not None)
                check(f"{main}: month arrived")
        window._go_next()
        check(f"{main}: next week")
        window._go_previous()
        check(f"{main}: previous week")
    window._open_focus_screen()
    check("Focus opened")
    window._close_focus_screen()
    check("Focus closed")
    zooms = [
        button
        for button in window.week_table.findChildren(QPushButton)
        if button.objectName().endswith(("ZoomIn", "ZoomOut")) and button.isEnabled()
    ]
    assert zooms, "the week's zoom buttons were not found"
    for button in zooms:
        button.click()
        check(f"zoom {button.objectName()}")
    window.toast.show_message("Moved History essay to Fri 18:00.", "Undo", lambda: None)
    check("a notice said")
    window.toast.hide()
    wrong = {what: sorted(set(found)) for what, found in seen if found}
    assert wrong == {}, "something moved at Off"
    assert starts == [], "a clock started at Off"


def test_a_sheet_at_off_has_a_plain_backdrop_and_takes_it_away_when_it_closes(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    go_off(qapp, window)
    seen: list[list[str]] = []

    def run(dialog: HomeworkDialog) -> int:
        dialog.show()
        qapp.processEvents()
        seen.append(moving(window))
        dialog.reject()
        seen.append(moving(window))
        return 0

    monkeypatch.setattr(HomeworkDialog, "exec", run)
    window._add_homework()
    qapp.processEvents()
    seen.append(moving(window))
    assert seen == [[], [], []]
    assert not motion.busy()




def test_animations_off_means_no_animation_anywhere(qapp: QApplication) -> None:  # noqa: F811
    apply_ui_effects("off")
    hours = Hours(qapp)
    hours.canvas.set_week(LATER)
    assert hours.canvas._slides == {} and hours.canvas._fresh == set(), "blocks are simply where they are"
    hours.window.close()
    stack, _first, second = two_pages(qapp)
    switch_page(stack, second, app_level())
    assert pictures(stack) == [] and second.graphicsEffect() is None
    stack.close()
    dialog = Dialog()
    QVBoxLayout(dialog).addWidget(QLabel("Nothing moves"))
    dialog.show()
    qapp.processEvents()
    assert dialog.windowOpacity() == 1.0
    assert [child for child in dialog.findChildren(QWidget) if child.graphicsEffect()] == []
    dialog.close()
