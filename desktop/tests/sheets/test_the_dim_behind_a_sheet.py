"""The dim behind a sheet starts at the click, and the sheet is built behind it. How dark the dim is,
is a look: pictures/_sheets_g13.py.

Order is counted, never timed: a constructor that records what is on screen when it runs sees whether
the dim was already there.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QStandardPaths, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from desktop.native import motion
from desktop.native import window as window_module
from desktop.native.feel import set_current
from desktop.native.motion import EASE_MS, apply_ui_effects, busy, duration
from desktop.native.widgets import Dialog, HomeworkDialog, SheetShade, dim_window
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.sheets.support_dialogs import when_open
from desktop.tests.test_feel import _host
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import free


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-sheet-dim-test"])


@pytest.fixture(autouse=True)
def motion_is_put_back() -> Iterator[None]:
    yield
    apply_ui_effects("normal")
    set_current(None)


def shades(host: QWidget) -> list[SheetShade]:
    """The dims over `host`, found without findChildren, which would hand a sheet to the window."""
    return [child for child in host.children() if isinstance(child, SheetShade)]


def drained(qapp: QApplication) -> None:
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()


def watch_the_build(
    monkeypatch: pytest.MonkeyPatch,
    window: NativeWindow,  # noqa: F811
    seen: list[dict],
) -> None:
    """HomeworkDialog records the dim as it is when its constructor starts, then builds as usual. exec
    is left out so the test decides what the sheet does next."""

    class Recorded(HomeworkDialog):
        def __init__(self, *args: object, **kwargs: object) -> None:
            on_screen = [shade for shade in shades(window) if shade.isVisible()]
            seen.append(
                {
                    "dims": len(on_screen),
                    "covers": bool(on_screen) and on_screen[0].geometry() == window.rect(),
                    "opacity": None,
                    "progress": on_screen[0].dim_progress if on_screen else 0.0,
                    "fading": on_screen[0].fading if on_screen else False,
                }
            )
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(window_module, "HomeworkDialog", Recorded)


def test_the_dim_is_up_and_already_fading_before_the_sheet_is_built(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    apply_ui_effects("normal")
    seen: list[dict] = []
    watch_the_build(monkeypatch, window, seen)
    monkeypatch.setattr(HomeworkDialog, "exec", lambda self: 0)
    window._add_homework()
    assert len(seen) == 1
    assert seen[0]["dims"] == 1, "one dim is shown when the constructor starts"
    assert seen[0]["covers"], "and it covers the whole window"
    assert seen[0]["fading"] and seen[0]["progress"] > 0, (
        "a frame of the fade has already been drawn, not only started"
    )


def test_the_sheet_adopts_the_dim_and_it_never_starts_over(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    apply_ui_effects("normal")
    made: list[HomeworkDialog] = []
    before: list[float] = []
    after: list[float] = []

    def run(dialog: HomeworkDialog) -> int:
        made.append(dialog)
        (dim,) = shades(window)
        before.append(dim.dim_progress)
        dialog.show()
        (only,) = shades(window)
        assert only is dim, "the sheet uses the dim it was given, not a second one"
        after.append(only.dim_progress)
        wait_until(qapp, lambda: not busy())
        return 0

    monkeypatch.setattr(HomeworkDialog, "exec", run)
    window._add_homework()
    assert after[0] >= before[0], "showing the sheet does not take the dim back to nothing"
    assert before[0] > 0
    free(made[0])


def test_the_dim_has_finished_fading_and_holds_a_still_when_the_sheet_is_up(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    apply_ui_effects("normal")
    landed: dict[str, object] = {}

    def run(dialog: HomeworkDialog) -> int:
        dialog.show()
        wait_until(qapp, lambda: not busy())
        (dim,) = shades(window)
        landed["fading"] = dim.fading
        landed["progress"] = dim.dim_progress
        landed["has_still"] = dim.has_still
        landed["covers"] = dim.geometry() == window.rect()
        return 0

    monkeypatch.setattr(HomeworkDialog, "exec", run)
    window._add_homework()
    assert landed["fading"] is False, "the fade has finished"
    assert landed["progress"] == 1.0
    assert landed["has_still"] is True
    assert landed["covers"]


@pytest.mark.parametrize("style_key", ["plain", "night", "dashboard", "retro"])
def test_the_dim_finishes_the_same_way_in_every_design(qapp: QApplication, style_key: str) -> None:
    apply_ui_effects("normal")
    host, _ctx = _host(qapp, style_key)
    dim = dim_window(host)
    # The dim waits for its sheet; the sheet that takes it lets the fade go on.
    sheet = Dialog(host, sheet=True)
    sheet.card_body("A sheet")
    sheet.show()
    wait_until(qapp, lambda: not busy())
    assert not dim.fading
    assert dim.dim_progress == 1.0
    assert dim.has_still
    assert dim.geometry() == host.rect()
    sheet.close()
    free(sheet)
    free(host)


def test_resizing_the_window_replaces_the_still_with_a_live_dim(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    apply_ui_effects("normal")
    seen: list[tuple[bool, bool, bool]] = []

    def run(dialog: HomeworkDialog) -> int:
        dialog.show()
        qapp.processEvents()
        (dim,) = shades(window)
        assert dim.has_still
        window.resize(1360, 900)
        qapp.processEvents()
        seen.append(
            (
                dim.has_still,
                dim.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground),
                dim.geometry() == window.rect(),
            )
        )
        dialog.reject()
        return 0

    monkeypatch.setattr(HomeworkDialog, "exec", run)
    window._add_homework()
    assert seen == [(False, True, True)]


def test_closing_the_sheet_takes_the_dim_with_it(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    apply_ui_effects("normal")

    def run(dialog: HomeworkDialog) -> int:
        dialog.show()
        qapp.processEvents()
        assert any(shade.isVisible() for shade in shades(window))
        dialog.reject()
        return 0

    monkeypatch.setattr(HomeworkDialog, "exec", run)
    window._add_homework()
    drained(qapp)
    assert shades(window) == []


def test_escape_while_the_dim_is_still_fading_closes_it_cleanly(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    apply_ui_effects("normal")
    window.resize(1280, 800)
    qapp.processEvents()

    seen: dict[str, object] = {}

    def press(sheet: QDialog) -> None:
        seen["mid_fade"] = isinstance(sheet, Dialog) and busy()
        QTest.keyClick(sheet, Qt.Key.Key_Escape)

    real_exec = Dialog.exec
    checks: list[Callable[[], None]] = []

    def run(dialog: Dialog) -> int:
        # Armed here, not at the click: the first frames of the dim are drawn while the sheet is built.
        checks.append(when_open(press))
        return real_exec(dialog)

    monkeypatch.setattr(HomeworkDialog, "exec", run)
    window._add_homework()
    checks[0]()
    assert seen["mid_fade"], "Esc came while the fade was still running"
    wait_until(qapp, lambda: not busy())
    drained(qapp)
    assert shades(window) == []
    assert QApplication.activeModalWidget() is None


def test_with_animations_off_the_dim_is_there_at_once(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    apply_ui_effects("off")
    assert duration(EASE_MS) == 0
    seen: list[dict] = []
    watch_the_build(monkeypatch, window, seen)
    states: list[tuple[bool, float]] = []

    def run(dialog: HomeworkDialog) -> int:
        (dim,) = shades(window)
        states.append((dim.fading, dim.dim_progress))
        assert not busy(), "nothing is moving"
        return 0

    monkeypatch.setattr(HomeworkDialog, "exec", run)
    window._add_homework()
    assert seen[0]["dims"] == 1 and seen[0]["opacity"] is None, "no fade: the dim is plain and whole"
    assert states == [(False, 1.0)]


def test_a_sheet_that_fails_to_build_leaves_no_dim(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    apply_ui_effects("normal")

    class Broken(HomeworkDialog):
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise RuntimeError("the form could not be built")

    monkeypatch.setattr(window_module, "HomeworkDialog", Broken)
    with pytest.raises(RuntimeError, match="could not be built"):
        window._add_homework()
    drained(qapp)
    assert shades(window) == []
    assert not busy()


def test_a_sheet_that_is_built_but_never_runs_leaves_no_dim(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    apply_ui_effects("normal")

    def run(_dialog: HomeworkDialog) -> int:
        raise RuntimeError("could not open")

    monkeypatch.setattr(HomeworkDialog, "exec", run)
    with pytest.raises(RuntimeError, match="could not open"):
        window._add_homework()
    drained(qapp)
    assert shades(window) == []


def test_every_on_demand_homework_sheet_dims_first(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """Homework sheets built on demand start after the dim, not before it."""
    apply_ui_effects("normal")
    dims: list[int] = []

    def counted(original: type) -> type:
        class Counted(original):  # type: ignore[valid-type, misc]
            def __init__(self, *args: object, **kwargs: object) -> None:
                dims.append(sum(shade.isVisible() for shade in shades(window)))
                super().__init__(*args, **kwargs)

        return Counted

    monkeypatch.setattr(window_module, "HomeworkDialog", counted(HomeworkDialog))
    monkeypatch.setattr(Dialog, "exec", lambda self: 0)
    openers: list[Callable[[], None]] = [
        window._add_homework,
        lambda: window._add_homework_due("2026-10-12"),
        lambda: window._add_from_chip("assignments"),
    ]
    for opener in openers:
        opener()
        drained(qapp)
    assert dims == [1] * len(openers)
    assert shades(window) == []


def test_a_slow_build_does_not_make_the_dim_jump_ahead(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """The dim waits for the sheet: however long the build takes, the fade goes on from where its first
    frame left it, rather than leaping by the build's length in one frame."""
    apply_ui_effects("normal")
    seen: list[dict] = []
    real_now = motion.now_ms

    class Slow(HomeworkDialog):
        def __init__(self, *args: object, **kwargs: object) -> None:
            (dim,) = shades(window)
            seen.append({"at_build": dim.dim_progress})
            super().__init__(*args, **kwargs)
            # The build took longer than the whole fade: the time the animations read has moved on by
            # that much, as if the build had run that long. A clock left running would be at its end.
            late = duration(EASE_MS) + 50
            monkeypatch.setattr(motion, "now_ms", lambda: real_now() + late)

    made: list[HomeworkDialog] = []

    def run(dialog: HomeworkDialog) -> int:
        made.append(dialog)
        dialog.show()
        # Whatever is overdue runs now: a clock that ran through the build is past its end and lands
        # the dim in one step.
        for _ in range(3):
            qapp.processEvents()
        (dim,) = shades(window)
        seen.append({"at_show": dim.dim_progress, "fading": dim.fading})
        wait_until(qapp, lambda: not busy())
        return 0

    monkeypatch.setattr(window_module, "HomeworkDialog", Slow)
    monkeypatch.setattr(Slow, "exec", run)
    window._add_homework()
    assert seen[0]["at_build"] > 0
    assert seen[1]["fading"], "the fade is still going when the sheet shows"
    assert seen[1]["at_show"] == pytest.approx(seen[0]["at_build"], abs=0.05), (
        "the dim held still while it waited, and goes on from there"
    )
    made[0].close()
    free(made[0])


def test_the_dim_leaves_in_the_same_instant_as_its_sheet(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """The dim lingered a frame after a sheet closed. It was only deleted later, so it stayed on screen
    until the event loop got to it."""
    seen: list[tuple[bool, bool]] = []

    def run(dialog: HomeworkDialog) -> int:
        dialog.show()
        qapp.processEvents()
        (dim,) = shades(window)
        wait_until(qapp, lambda: not busy())
        dialog.reject()
        # No event has run since the sheet went: the dim must already be gone with it.
        seen.append((dialog.isVisible(), dim.isVisible()))
        return 0

    for level in ("normal", "extra", "off"):
        apply_ui_effects(level)
        monkeypatch.setattr(HomeworkDialog, "exec", run)
        window._add_homework()
        drained(qapp)
    assert seen == [(False, False)] * 3


def test_a_sheet_closed_while_its_dim_is_still_fading_takes_the_dim_down_at_once(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    apply_ui_effects("extra")
    seen: list[tuple[bool, bool]] = []

    def run(dialog: HomeworkDialog) -> int:
        dialog.show()
        qapp.processEvents()
        (dim,) = shades(window)
        assert busy(), "the fade is still going"
        dialog.reject()
        seen.append((dialog.isVisible(), dim.isVisible()))
        return 0

    monkeypatch.setattr(HomeworkDialog, "exec", run)
    window._add_homework()
    drained(qapp)
    assert seen == [(False, False)]
    assert not busy(), "the fade went with the dim"
