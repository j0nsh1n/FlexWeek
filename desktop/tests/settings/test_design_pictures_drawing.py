"""The design pictures on Settings and Setup: each takes about a tenth of a second to draw, so they are
drawn one a turn, only when nothing moves, and not before Settings has slid in."""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QApplication, QWidget

    from desktop.native import motion as moving
    from desktop.native.layouts import dialog
    from desktop.native.layouts.dialog import DesignPicker
    from desktop.native.motion import OVER_MS, apply_ui_effects, duration
    from desktop.tests.motion_support import ManualTime, manual_time  # noqa: F401
    from desktop.tests.settings.support_motion import THROUGH_MS, move_on
    from desktop.tests.window_support import qapp  # noqa: F401


@pytest.fixture(autouse=True)
def motion_is_put_back() -> Iterator[None]:
    apply_ui_effects("normal")
    yield
    apply_ui_effects("normal")


class Drawn:
    """Stands in for the pictures' cache and counts what is drawn, and holds the timers the picker
    asks for so a test runs each one itself, in the order and at the delay it was asked for."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.drawn: list[int] = []
        self.timers: list[tuple[int, object]] = []
        drawn = self.drawn

        class Counting:
            def get(self, *_args: object) -> QPixmap:
                drawn.append(1)
                return QPixmap(4, 4)

        monkeypatch.setattr(dialog, "Previews", Counting)
        monkeypatch.setattr(
            dialog.QTimer, "singleShot", lambda delay, _context, call: self.timers.append((delay, call))
        )

    def asked_for(self, picker: DesignPicker) -> list[int]:
        """The delays of the draws the picker has asked for and not had run."""
        return [delay for delay, call in self.timers if call == picker._draw_next]

    def run_next(self, picker: DesignPicker) -> None:
        for at, (_delay, call) in enumerate(self.timers):
            if call == picker._draw_next:
                del self.timers[at]
                picker._draw_next()
                return
        raise AssertionError("the picker asked for no further draw")


def test_the_design_pictures_wait_until_settings_has_slid_in(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """Each design's picture takes over 100 ms to draw, and they were drawn one after another from the
    moment Settings was built, so the first slide in got three frames. The first is held until a slide
    at the slowest level has landed."""
    seen = Drawn(monkeypatch)
    picker = DesignPicker("plan", "designs", "Design", "slate")
    assert picker.cards
    picker.show()
    assert seen.drawn == [], "nothing is drawn while the page could still be sliding in"
    first_asked = seen.asked_for(picker)[0]
    assert first_asked >= duration(OVER_MS, "extra"), "and the first is asked for after the slide"
    for _ in range(len(picker.cards)):
        seen.run_next(picker)
    assert len(seen.drawn) == len(picker.cards), "then every picture is drawn"
    picker.close()
    picker.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_a_design_picture_waits_while_something_moves(
    qapp: QApplication, manual_time: ManualTime, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """A picture takes about a tenth of a second, so drawn in the middle of a fade it held that fade
    still for as long (Retro's week to day, 2026-10-08). It waits until nothing moves."""
    seen = Drawn(monkeypatch)
    picker = DesignPicker("plan", "designs", "Design", "slate")
    owner = QWidget()
    owner.resize(40, 40)
    owner.show()
    moving.appear(owner, "normal")
    assert moving.busy()
    picker._draw_next()
    assert seen.drawn == [], "nothing is drawn while the fade runs"
    move_on(manual_time, THROUGH_MS)
    assert not moving.busy()
    picker._draw_next()
    assert seen.drawn == [1], "once the fade has ended the picture is drawn"
    for widget in (picker, owner):
        widget.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_design_pictures_are_drawn_one_a_turn_and_can_be_drawn_ahead(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """Each design picture takes about a tenth of a second. Chained on a zero timer they become one
    long turn. Ahead of time, while Settings is not on screen, they can all be drawn now."""
    seen = Drawn(monkeypatch)
    picker = DesignPicker("plan", "designs", "Design", "slate")
    picker._draw_next()
    assert len(seen.drawn) == 1
    assert len(seen.asked_for(picker)) >= 1, "the next picture is asked for on a later turn"
    assert len(seen.drawn) == 1, "the next picture waits until the next turn"
    picker.warm()
    assert len(seen.drawn) == len(picker.cards)
    picker.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_visible_design_pictures_wait_for_motion_but_not_forever(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    picker = dialog.DesignPicker("plan", "designs", "Design", "slate")
    picker.show()
    calls: list[int] = []
    monkeypatch.setattr(picker, "_draw_one", lambda: calls.append(1) or False)
    monkeypatch.setattr(dialog.QTimer, "singleShot", lambda *_: None)
    owner = QWidget()
    owner.show()
    clock = moving.Clock(owner)
    clock.start(10000, lambda _: None)
    picker._draw_next()
    assert calls == [], "visible previews must wait while a fade runs"
    clock.stop()
    picker._draw_next()
    assert calls == [1], "drawing resumes as soon as motion stops"
    calls.clear()
    clock.start(10000, lambda _: None)
    for _ in range(10):
        picker._draw_next()
        assert calls == [], "ten waits are allowed before drawing through a stuck clock"
    picker._draw_next()
    assert calls == [1]
    clock.stop()
    picker.close()
    owner.close()


@pytest.mark.parametrize("design", ["timeline", "mission", "bento", "retro", "clay", "one", "dial"])
def test_a_design_preview_renders_once_at_its_final_width(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, design: str  # noqa: F811
) -> None:
    from desktop.native import previews
    from desktop.native.layouts.views import VIEW_CLASSES

    apply_ui_effects("off")
    calls: list[int] = []
    cls = VIEW_CLASSES[design]
    render = cls.render

    def counted(self, scene, changed):  # type: ignore[no-untyped-def]
        calls.append(self.width())
        return render(self, scene, changed)

    monkeypatch.setattr(cls, "render", counted)
    previews.render(design, None, "slate", None, 206)
    assert calls == [1280], "a preview must not rebuild after a stale narrow first render"
