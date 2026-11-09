"""The Add fixed time sheet is built in a quiet moment before the click, so the click only fills it in
and shows it with its dim. What a ready sheet must still get right: the times and category asked for,
focus on the title, no dim left behind, and no spare kept across a change of look or account.

Order is counted, never timed: a constructor that records what is on screen when it runs sees whether
the dim was already there.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QStandardPaths, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from desktop.native import window as window_module
from desktop.native.feel import set_current
from desktop.native.look import sanitize_look
from desktop.native.motion import apply_ui_effects, busy
from desktop.native.widgets import BlockDialog, SheetShade
from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.waiting import wait_until


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    QStandardPaths.setTestModeEnabled(True)
    yield QApplication.instance() or QApplication(["flexweek-fixed-time-ready-test"])


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


def spare_is_ready(qapp: QApplication, window: NativeWindow) -> None:  # noqa: F811
    wait_until(qapp, lambda: getattr(window, "_block_spare", None) is not None)


def test_fixed_time_is_built_before_the_click_and_shows_with_its_dim(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    apply_ui_effects("normal")
    spare_is_ready(qapp, window)
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
    spare_is_ready(qapp, window)
    opened: list[tuple[list[int], str, object]] = []

    def run(dialog: BlockDialog) -> int:
        opened.append(
            (dialog.day_picker.days(), dialog.start.time().toString("HH:mm"), dialog.category.currentData())
        )
        return 0

    monkeypatch.setattr(BlockDialog, "exec", run)
    window.session.armed_category = "class"
    window._add_fixed_at(1, 615)
    spare_is_ready(qapp, window)
    window.session.armed_category = "exercise"
    window._add_fixed_at(4, 975)
    assert opened == [([1], "10:15", "class"), ([4], "16:15", "exercise")]


def test_a_range_drawn_on_the_hours_keeps_its_own_times_in_a_ready_sheet(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """Drawing 16:00 to 17:00 for School on Wednesday is that hour on that day, not School's preset week
    of 08:00 to 14:30, which an Add fixed time for School starts from."""
    spare_is_ready(qapp, window)
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
    spare_is_ready(qapp, window)
    old = window._block_spare
    knobs = {**window._look.get("knobs", {}), "text": "large"}
    window._look = sanitize_look({**window._look, "knobs": knobs})
    window._apply_appearance()
    spare_is_ready(qapp, window)
    assert window._block_spare is not old


def test_editing_a_block_still_builds_its_saved_values_on_demand(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
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


def test_a_ready_fixed_time_opens_focused_on_title_and_escape_removes_its_dim(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    spare_is_ready(qapp, window)
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


def test_a_failed_idle_build_falls_back_with_a_clean_dim(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
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


def test_an_account_change_discards_the_spare_before_another_account_opens_it(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    spare_is_ready(qapp, window)
    window._block_spare.title.setText("Private first account title")
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


def test_with_motion_off_the_ready_sheet_and_dim_show_in_one_frame(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    apply_ui_effects("off")
    spare_is_ready(qapp, window)
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
