"""J15: the dim behind a sheet starts at the click, and the sheet is built behind it.

Order is counted, never timed: a constructor that records what is on screen when it runs sees whether
the dim was already there.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPoint, Qt, QTimer
from PySide6.QtGui import QImage, QRegion
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from desktop.native import window as window_module
from desktop.native.feel import set_current
from desktop.native.motion import EASE_MS, apply_ui_effects, busy, duration
from desktop.native.widgets import SHEET_DIM, Dialog, HomeworkDialog, SheetShade
from desktop.native.window import NativeWindow
from desktop.tests.test_feel import _host
from desktop.tests.window_support import free, qapp, server, signed_out, wait_until, window  # noqa: F401

# What SHEET_DIM of black is as an alpha byte; written out so a change of the dim is a change here.
DIM_ALPHA = 102


@pytest.fixture(autouse=True)
def motion_is_put_back() -> Iterator[None]:
    yield
    apply_ui_effects("normal")
    set_current(None)


def shades(host: QWidget) -> list[SheetShade]:
    """The dims over `host`, found without findChildren, which would hand a sheet to the window."""
    return [child for child in host.children() if isinstance(child, SheetShade)]


def drained(qapp: QApplication) -> None:  # noqa: F811
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()


def painted(shade: SheetShade) -> tuple[int, int, int, int]:
    """What the dim paints by itself, on nothing, as red, green, blue and alpha. (grab() would put it
    on an opaque backdrop and always read 255.)"""
    image = QImage(shade.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    shade.render(image, QPoint(), QRegion(), QWidget.RenderFlag.DrawChildren)
    return image.pixelColor(5, 5).getRgb()


def painted_alpha(shade: SheetShade) -> int:
    return painted(shade)[3]


def watch_the_build(
    monkeypatch: pytest.MonkeyPatch, window: NativeWindow, seen: list[dict]  # noqa: F811
) -> None:
    """HomeworkDialog records the dim as it is when its constructor starts, then builds as usual. exec
    is left out so the test decides what the sheet does next."""

    class Recorded(HomeworkDialog):
        def __init__(self, *args: object, **kwargs: object) -> None:
            on_screen = [shade for shade in shades(window) if shade.isVisible()]
            effect = on_screen[0].graphicsEffect() if on_screen else None
            seen.append(
                {
                    "dims": len(on_screen),
                    "covers": bool(on_screen) and on_screen[0].geometry() == window.rect(),
                    "opacity": getattr(effect, "opacity", None),
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
    assert seen[0]["opacity"] is not None and seen[0]["opacity"] > 0, (
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
        before.append(dim.graphicsEffect().opacity)
        dialog.show()
        (only,) = shades(window)
        assert only is dim, "the sheet uses the dim it was given, not a second one"
        after.append(only.graphicsEffect().opacity)
        wait_until(qapp, lambda: not busy())
        return 0

    monkeypatch.setattr(HomeworkDialog, "exec", run)
    window._add_homework()
    assert after[0] >= before[0], "showing the sheet does not take the dim back to nothing"
    assert before[0] > 0
    free(made[0])


def test_the_dim_ends_at_the_same_black_it_always_did(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    apply_ui_effects("normal")
    assert round(255 * SHEET_DIM) == DIM_ALPHA
    landed: dict[str, object] = {}

    def run(dialog: HomeworkDialog) -> int:
        dialog.show()
        wait_until(qapp, lambda: not busy())
        (dim,) = shades(window)
        landed["effect"] = dim.graphicsEffect()
        landed["alpha"] = painted_alpha(dim)
        landed["colour"] = painted(dim)[:3]
        landed["covers"] = dim.geometry() == window.rect()
        return 0

    monkeypatch.setattr(HomeworkDialog, "exec", run)
    window._add_homework()
    assert landed["effect"] is None, "the fade has finished"
    assert landed["alpha"] == DIM_ALPHA
    assert landed["colour"] == (0, 0, 0)
    assert landed["covers"]


@pytest.mark.parametrize("style_key", ["plain", "night", "dashboard", "retro"])
def test_the_dim_is_the_same_in_every_design(qapp: QApplication, style_key: str) -> None:  # noqa: F811
    from desktop.native.widgets import dim_window

    apply_ui_effects("normal")
    host, _ctx = _host(qapp, style_key)
    dim = dim_window(host)
    # The dim waits for its sheet; the sheet that takes it lets the fade go on.
    sheet = Dialog(host, sheet=True)
    sheet.card_body("A sheet")
    sheet.show()
    wait_until(qapp, lambda: not busy())
    assert painted_alpha(dim) == DIM_ALPHA
    assert painted(dim)[:3] == (0, 0, 0)
    assert dim.geometry() == host.rect()
    sheet.close()
    free(sheet)
    free(host)


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

    def press() -> None:
        sheet = QApplication.activeModalWidget()
        seen["mid_fade"] = isinstance(sheet, Dialog) and busy()
        QTest.keyClick(sheet, Qt.Key.Key_Escape)

    real_exec = Dialog.exec

    def run(dialog: Dialog) -> int:
        # Started here, not at the click: the first frames of the dim are drawn while the sheet is built.
        QTimer.singleShot(10, press)
        return real_exec(dialog)

    monkeypatch.setattr(HomeworkDialog, "exec", run)
    window._add_homework()
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
    states: list[tuple[object, int]] = []

    def run(dialog: HomeworkDialog) -> int:
        (dim,) = shades(window)
        states.append((dim.graphicsEffect(), painted_alpha(dim)))
        assert not busy(), "nothing is moving"
        return 0

    monkeypatch.setattr(HomeworkDialog, "exec", run)
    window._add_homework()
    assert seen[0]["dims"] == 1 and seen[0]["opacity"] is None, "no fade: the dim is plain and whole"
    assert states == [(None, DIM_ALPHA)]


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


def test_fixed_time_is_built_before_the_click_and_shows_with_its_dim(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    from desktop.native.widgets import BlockDialog

    apply_ui_effects("normal")
    wait_until(qapp, lambda: getattr(window, "_block_spare", None) is not None)
    built_inside_click = 0
    clicking = False
    visible_together: list[tuple[bool, bool]] = []
    original_init = BlockDialog.__init__

    class Watched(BlockDialog):
        def __init__(self, *args: object, **kwargs: object) -> None:
            nonlocal built_inside_click
            built_inside_click += int(clicking)
            original_init(self, *args, **kwargs)

    def run(dialog: BlockDialog) -> int:
        dialog.show()
        visible_together.append((dialog.isVisible(), any(shade.isVisible() for shade in shades(window))))
        return 0

    monkeypatch.setattr(window_module, "BlockDialog", Watched)
    monkeypatch.setattr(BlockDialog, "exec", run)
    clicking = True
    window._add_fixed_at(2, 735)
    clicking = False
    assert built_inside_click == 0, "the dialog was constructed while handling the click"
    assert visible_together == [(True, True)], "the dialog and dim are visible together"


def test_consecutive_fixed_time_opens_use_each_requested_value(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    from desktop.native.widgets import BlockDialog

    wait_until(qapp, lambda: getattr(window, "_block_spare", None) is not None)
    opened: list[tuple[list[int], str, object]] = []

    def run(dialog: BlockDialog) -> int:
        opened.append(
            (dialog.day_picker.days(), dialog.start.time().toString("HH:mm"), dialog.category.currentData())
        )
        return 0

    monkeypatch.setattr(BlockDialog, "exec", run)
    window.session.armed_category = "class"
    window._add_fixed_at(1, 615)
    wait_until(qapp, lambda: getattr(window, "_block_spare", None) is not None)
    window.session.armed_category = "exercise"
    window._add_fixed_at(4, 975)
    assert opened == [([1], "10:15", "class"), ([4], "16:15", "exercise")]


def test_a_range_drawn_on_the_hours_keeps_its_own_times_in_a_prebuilt_sheet(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """Drawing 16:00 to 17:00 for School on Wednesday is that hour on that day, not School's preset week
    of 08:00 to 14:30, which an Add fixed time for School starts from."""
    from desktop.native.widgets import BlockDialog

    wait_until(qapp, lambda: getattr(window, "_block_spare", None) is not None)
    opened: list[tuple[list[int], str, str]] = []

    def run(dialog: BlockDialog) -> int:
        opened.append(
            (
                dialog.day_picker.days(),
                dialog.start.time().toString("HH:mm"),
                dialog.end.time().toString("HH:mm"),
            )
        )
        return 0

    monkeypatch.setattr(BlockDialog, "exec", run)
    window.session.armed_category = "class"
    window._create_range(2, 16 * 60, 17 * 60)
    assert opened == [([2], "16:00", "17:00")]


def test_a_change_of_look_drops_the_spare_built_in_the_old_one(
    qapp: QApplication, window: NativeWindow  # noqa: F811
) -> None:
    """A spare built before Large text was chosen would open at the old size and colours."""
    from desktop.native.look import sanitize_look

    wait_until(qapp, lambda: getattr(window, "_block_spare", None) is not None)
    old = window._block_spare
    knobs = {**window._look.get("knobs", {}), "text": "large"}
    window._look = sanitize_look({**window._look, "knobs": knobs})
    window._apply_appearance()
    wait_until(qapp, lambda: getattr(window, "_block_spare", None) is not None)
    assert window._block_spare is not old


def test_editing_a_block_still_builds_its_saved_values_on_demand(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    from desktop.native.widgets import BlockDialog

    block = {
        "id": "edit-me",
        "kind": "locked",
        "title": "Saved lesson",
        "days": [3],
        "start": "09:30",
        "duration_min": 45,
        "category": "class",
        "missed_days": [],
    }
    builds = 0
    original = BlockDialog.__init__

    def counted(self, *args: object, **kwargs: object) -> None:
        nonlocal builds
        builds += 1
        original(self, *args, **kwargs)

    seen: list[tuple[str, list[int], str]] = []

    def run(dialog: BlockDialog) -> int:
        seen.append((dialog.title.text(), dialog.day_picker.days(), dialog.start.time().toString("HH:mm")))
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(BlockDialog, "__init__", counted)
    monkeypatch.setattr(BlockDialog, "exec", run)
    window._commit_block(window._sheet(lambda: BlockDialog(window, block)))
    assert builds == 1
    assert seen == [("Saved lesson", [3], "09:30")]
    saved = next(item for item in window.session.blocks if item["id"] == "edit-me")
    assert (saved["title"], saved["days"], saved["start"], saved["duration_min"]) == (
        "Saved lesson",
        [3],
        "09:30",
        45,
    )


def test_prebuilt_fixed_time_opens_focused_on_title_and_escape_removes_its_dim(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    from desktop.native.widgets import BlockDialog

    wait_until(qapp, lambda: getattr(window, "_block_spare", None) is not None)
    seen: list[bool] = []

    def run(dialog: BlockDialog) -> int:
        dialog.show()
        qapp.processEvents()
        seen.append(QApplication.focusWidget() is dialog.title)
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
        return 0

    monkeypatch.setattr(BlockDialog, "exec", run)
    window._add_fixed_at(5, 1020)
    drained(qapp)
    assert seen == [True], "Title owns keyboard focus when the sheet opens"
    assert shades(window) == [], "Esc closes both the sheet and its dim"


def test_failed_idle_prebuild_falls_back_with_a_clean_dim(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    from desktop.native.widgets import BlockDialog

    real_dialog = window_module.BlockDialog

    def fail_build(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("prebuild failed")

    window._discard_block_spare()
    monkeypatch.setattr(window_module, "BlockDialog", fail_build)
    window._prepare_block_spare()
    assert window._block_spare is None
    assert shades(window) == []

    built_with_dim: list[int] = []
    original_init = BlockDialog.__init__

    def recorded_init(self: BlockDialog, *args: object, **kwargs: object) -> None:
        built_with_dim.append(sum(shade.isVisible() for shade in shades(window)))
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(window_module, "BlockDialog", real_dialog)
    monkeypatch.setattr(BlockDialog, "__init__", recorded_init)
    monkeypatch.setattr(BlockDialog, "exec", lambda _self: 0)
    window._add_fixed_at(2, 735)
    drained(qapp)
    assert built_with_dim[0] == 1, "the fallback still builds behind the dim"
    assert shades(window) == [], "the failed spare left no dim behind"


def test_account_change_discards_the_spare_before_another_account_opens_it(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    from desktop.native.widgets import BlockDialog

    wait_until(qapp, lambda: getattr(window, "_block_spare", None) is not None)
    old_spare = window._block_spare
    old_spare.title.setText("Private first account title")
    window.session.account = {"id": "other-account", "username": "other"}
    window._on_account(window.session.account)
    assert window._block_spare is None
    assert window._block_spare_account is None

    opened: list[str] = []

    def run(dialog: BlockDialog) -> int:
        opened.append(dialog.title.text())
        return 0

    monkeypatch.setattr(BlockDialog, "exec", run)
    window._add_fixed_at(3, 600)
    assert opened == [""]


def test_motion_off_keeps_the_prebuilt_sheet_and_dim_in_one_frame(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    from desktop.native.widgets import BlockDialog

    apply_ui_effects("off")
    wait_until(qapp, lambda: getattr(window, "_block_spare", None) is not None)
    together: list[tuple[bool, bool]] = []

    def run(dialog: BlockDialog) -> int:
        dialog.show()
        qapp.processEvents()
        together.append((dialog.isVisible(), any(shade.isVisible() for shade in shades(window))))
        dialog.close()
        return 0

    monkeypatch.setattr(BlockDialog, "exec", run)
    window._add_fixed_at(1, 615)
    drained(qapp)
    assert together == [(True, True)]
    assert not busy()
    assert shades(window) == []


def test_a_slow_build_does_not_make_the_dim_jump_ahead(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """The dim waits for the sheet: however long the build takes, the fade goes on from where its first
    frame left it, rather than leaping by the build's length in one frame."""
    import time

    apply_ui_effects("normal")
    seen: list[dict] = []

    class Slow(HomeworkDialog):
        def __init__(self, *args: object, **kwargs: object) -> None:
            (dim,) = shades(window)
            seen.append({"at_build": dim.graphicsEffect().opacity})
            super().__init__(*args, **kwargs)
            # Longer than the whole fade: a clock left running would be at the end by now.
            time.sleep(duration(EASE_MS) / 1000 + 0.05)

    made: list[HomeworkDialog] = []

    def run(dialog: HomeworkDialog) -> int:
        made.append(dialog)
        dialog.show()
        # Whatever is overdue runs now, with no time passing: a clock that ran through the build is
        # past its end and lands the dim in one step.
        for _ in range(3):
            qapp.processEvents()
        (dim,) = shades(window)
        effect = dim.graphicsEffect()
        seen.append({"at_show": None if effect is None else effect.opacity})
        wait_until(qapp, lambda: not busy())
        return 0

    monkeypatch.setattr(window_module, "HomeworkDialog", Slow)
    monkeypatch.setattr(Slow, "exec", run)
    window._add_homework()
    assert seen[0]["at_build"] > 0
    assert seen[1]["at_show"] is not None, "the fade is still going when the sheet shows"
    assert seen[1]["at_show"] == pytest.approx(seen[0]["at_build"], abs=0.05), (
        "the dim held still while it waited, and goes on from there"
    )
    made[0].close()
    free(made[0])


def test_the_dim_leaves_in_the_same_instant_as_its_sheet(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """0.18.5 #97: the dim lingered a frame after a sheet closed. It was only deleted later, so it stayed
    on screen until the event loop got to it."""
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
