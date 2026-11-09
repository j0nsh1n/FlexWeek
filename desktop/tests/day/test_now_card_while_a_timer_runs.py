# ruff: noqa: F811
"""The Now card on the Material Day and My day screens while a focus timer exists: it names the timer
and goes back to it, says Session finished with Mark finished and Start again, says Finished with one
OK when the homework is already done, and where keyboard focus goes when its buttons change or go.

Thursday 17:00: School 08:00-14:30 is over, the History essay waits at 18:45. A replace question
that gets asked is answered Keep, so a wrongly asked question fails the test instead of hanging it.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.calendar import sunday_due  # noqa: E402
from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_material_day import root_bridge, seed_thursday  # noqa: E402
from desktop.tests.light_app import open_light  # noqa: E402, F401
from desktop.tests.material_support import pump, qml, show_material  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.window_support import qapp, settled  # noqa: E402, F401


@pytest.fixture()
def window(qapp: QApplication, open_light) -> Iterator[NativeWindow]:
    made = seed_thursday(qapp, open_light((1280, 800)), hour=17)
    try:
        yield made
    finally:
        made.session.reset_focus()


@pytest.fixture()
def keep_on_replace(monkeypatch: pytest.MonkeyPatch) -> None:
    """A replace question that gets asked is answered Keep instead of waiting on a modal sheet, so a
    wrongly asked question fails the test (through `asked`) instead of hanging it."""
    import desktop.native.window as window_module

    class Keep:
        answer = "keep"

        def __init__(self, *_args: object, **_kw: object) -> None:
            pass

        def exec(self) -> int:
            return 0

    monkeypatch.setattr(window_module, "ConfirmSheet", Keep)


def _card(root: QObject, scope: str) -> tuple[str, str, str]:
    """The Now card as the student reads it: title, line, button."""
    return tuple(  # type: ignore[return-value]
        str(qml(root, scope + name).property("text")) for name in ("NowTitle", "NowLine", "StartFocus")
    )


def _run_out(qapp: QApplication, window: NativeWindow, root: QObject, *, quick: bool = False) -> QObject:
    """A focus timer on today's first homework (or a quick one) that has run out and is not cleared."""
    session = window.session
    bridge = root_bridge(root)
    focus = bridge.property("focus")
    if quick:
        session.start_quick_focus()
    else:
        bridge.property("myday").startFocus()
    pump(qapp)
    focus.hide()
    session.focus["endsAt"] = session.now_ms() - 1
    session.tick_focus()
    settled(qapp, window)
    if quick:
        # A quick focus moves on to its break on its own; the card must still cope with it being over.
        session.focus.update({"phase": "ended", "running": False, "remainingMs": 0})
        session.focus_changed.emit()
    pump(qapp)
    assert session.focus["phase"] == "ended"
    return focus


def _add_bystander(qapp: QApplication, window: NativeWindow) -> None:
    """A second open homework with a block later today, so the Now card stays after the first is finished."""
    session = window.session
    session.add_homework(
        {
            "id": "bystander",
            "title": "Maths sheet",
            "due": sunday_due(session.week_start),
            "estimate_min": 30,
            "revision": 0,
        }
    )
    session.save()
    settled(qapp, window)
    work = next(block for block in session.blocks if block.get("assignment_id") == "bystander")
    work.update({"start": "20:00", "days": [3], "duration_min": 30})
    session.add_block(work)
    session.save()
    settled(qapp, window)
    assert not session.assignments["bystander"].get("completed")


def _assert_focus_on_a_visible_page_item(scene: object) -> None:
    held = scene.activeFocusItem()  # type: ignore[attr-defined]
    assert held is not None, "keyboard focus is nowhere"
    assert held.property("visible") is True, f"focus stayed on hidden {held.objectName()!r}"
    assert held.objectName() not in (
        "myDayStartFocus",
        "myDayMarkFinished",
        "dayStartFocus",
        "dayMarkFinished",
    )


def test_while_a_focus_timer_runs_the_now_card_names_it_and_goes_back_to_it(
    qapp: QApplication, window: NativeWindow, keep_on_replace: None
) -> None:
    session = window.session
    root = show_material(qapp, window)
    bridge = root_bridge(root)
    focus = bridge.property("focus")
    asked: list[tuple[str, str]] = []
    session.focus_replace_needed.connect(lambda *names: asked.append(names))
    bridge.property("myday").startFocus()
    pump(qapp)
    assert focus.property("open") is True
    focus.hide()
    session.focus["endsAt"] = session.now_ms() + 13 * 60_000
    session.tick_focus()
    pump(qapp)
    for page, scope in (("myday", "myDay"), ("day", "day")):
        bridge.showPage(page)
        pump(qapp)
        assert _card(root, scope) == ("History essay", "13 min left", "Back to History essay")
        started = dict(session.focus)
        qml(root, scope + "StartFocus").clicked.emit()
        pump(qapp)
        assert focus.property("open") is True
        assert asked == []
        assert session.focus == started  # the same timer, not a new one
        focus.hide()
        pump(qapp)
    session.focus["endsAt"] = session.now_ms() - 1
    session.tick_focus()
    settled(qapp, window)
    pump(qapp)
    assert session.focus["phase"] == "ended"
    for page, scope in (("myday", "myDay"), ("day", "day")):
        bridge.showPage(page)
        pump(qapp)
        assert _card(root, scope) == ("History essay", "Session finished", "Start again")


def test_a_finished_timer_makes_the_now_card_say_so_with_mark_finished_and_start_again(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = show_material(qapp, window)
    bridge = root_bridge(root)
    _run_out(qapp, window, root)
    title = window.session.focus["title"]
    for page, scope in (("myday", "myDay"), ("day", "day")):
        bridge.showPage(page)
        pump(qapp)
        assert _card(root, scope) == (title, "Session finished", "Start again")
        assert qml(root, scope + "MarkFinished").property("visible") is True
        assert qml(root, scope + "MarkFinished").property("text") == "Mark finished"


def test_mark_finished_on_the_now_card_marks_the_homework_done_and_clears_the_timer(
    qapp: QApplication, window: NativeWindow
) -> None:
    session = window.session
    root = show_material(qapp, window)
    bridge = root_bridge(root)
    _run_out(qapp, window, root)
    homework = session.focus["assignmentId"]
    assert not session.assignments[homework].get("completed")
    _add_bystander(qapp, window)
    bridge.showPage("myday")
    pump(qapp)
    qml(root, "myDayMarkFinished").clicked.emit()
    settled(qapp, window)
    pump(qapp)
    assert session.assignments[homework]["completed"] is True
    assert not session.assignments["bystander"].get("completed")
    assert session.focus is None
    assert not bridge.property("focus").property("open")
    assert qml(root, "myDayStartFocus").property("text") != "Start again"
    assert qml(root, "myDayMarkFinished").property("visible") is False
    for page, scope in (("myday", "myDay"), ("day", "day")):
        bridge.showPage(page)
        pump(qapp)
        assert "Session finished" not in _card(root, scope)


def test_a_finished_session_on_already_finished_homework_offers_only_ok(
    qapp: QApplication, window: NativeWindow, keep_on_replace: None
) -> None:
    """Finish-automatically can mark the homework done as the last session ends: nothing is left to
    mark or to start again, so the card says Finished with one OK that clears the timer."""
    session = window.session
    root = show_material(qapp, window)
    bridge = root_bridge(root)
    asked: list[tuple[str, str]] = []
    session.focus_replace_needed.connect(lambda *names: asked.append(names))
    _run_out(qapp, window, root)
    homework = session.focus["assignmentId"]
    title = session.focus["title"]
    session.complete_homework(homework, True)
    settled(qapp, window)
    for page, scope in (("myday", "myDay"), ("day", "day")):
        bridge.showPage(page)
        wait_until(qapp, lambda scope=scope: _card(root, scope)[1] == "Finished")
        assert _card(root, scope) == (title, "Finished", "OK")
        assert qml(root, scope + "MarkFinished").property("visible") is False
    before = dict(session.focus)
    qml(root, "dayStartFocus").clicked.emit()
    settled(qapp, window)
    pump(qapp)
    assert session.focus is None
    assert before["phase"] == "ended"
    assert asked == []
    assert not bridge.property("focus").property("open")
    assert session.assignments[homework]["completed"] is True
    for page, scope in (("myday", "myDay"), ("day", "day")):
        bridge.showPage(page)
        pump(qapp)
        assert _card(root, scope)[1] not in ("Finished", "Session finished")
        assert _card(root, scope)[2] != "OK"


def test_mark_finished_from_the_keyboard_leaves_focus_on_a_visible_button(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Mark finished hides itself, so keyboard focus must move to the card's button that stays."""
    session = window.session
    root = show_material(qapp, window)
    bridge = root_bridge(root)
    scene = window._material_page._quick.quickWindow()
    _run_out(qapp, window, root)
    _add_bystander(qapp, window)
    bridge.showPage("myday")
    pump(qapp)
    qml(root, "myDayMarkFinished").forceActiveFocus()
    pump(qapp)
    assert scene.activeFocusItem().objectName() == "myDayMarkFinished"
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_Space)
    settled(qapp, window)
    pump(qapp)
    assert session.focus is None
    held = scene.activeFocusItem()
    assert held is not None and held.property("visible") is True
    assert held.objectName() == "myDayStartFocus"


def test_mark_finished_on_the_days_last_homework_hides_the_card_and_focus_moves_to_something_visible(
    qapp: QApplication, window: NativeWindow
) -> None:
    """With nothing else today the whole Now card goes away: focus must not stay on its hidden button."""
    session = window.session
    root = show_material(qapp, window)
    bridge = root_bridge(root)
    scene = window._material_page._quick.quickWindow()
    _run_out(qapp, window, root)
    homework = session.focus["assignmentId"]
    for page in ("myday", "day"):
        bridge.showPage(page)
        pump(qapp)
        scope = "myDay" if page == "myday" else "day"
        qml(root, scope + "MarkFinished").forceActiveFocus()
        pump(qapp)
        assert scene.activeFocusItem().objectName() == scope + "MarkFinished"
        QTest.keyClick(window._material_page._quick, Qt.Key.Key_Space)
        settled(qapp, window)
        pump(qapp)
        assert session.focus is None
        assert qml(root, scope + "Now").property("visible") is False
        _assert_focus_on_a_visible_page_item(scene)
        session.complete_homework(homework, False)
        settled(qapp, window)
        _run_out(qapp, window, root)


def test_ok_on_a_finished_session_hides_the_card_and_focus_moves_to_something_visible(
    qapp: QApplication, window: NativeWindow, keep_on_replace: None
) -> None:
    """OK clears the timer; with nothing else today the card hides, so focus must leave its button."""
    session = window.session
    root = show_material(qapp, window)
    bridge = root_bridge(root)
    scene = window._material_page._quick.quickWindow()
    _run_out(qapp, window, root)
    homework = session.focus["assignmentId"]
    session.complete_homework(homework, True)
    settled(qapp, window)
    for page, scope in (("myday", "myDay"), ("day", "day")):
        bridge.showPage(page)
        wait_until(qapp, lambda scope=scope: _card(root, scope)[1] == "Finished")
        qml(root, scope + "StartFocus").forceActiveFocus()
        pump(qapp)
        assert scene.activeFocusItem().objectName() == scope + "StartFocus"
        QTest.keyClick(window._material_page._quick, Qt.Key.Key_Space)
        settled(qapp, window)
        pump(qapp)
        assert session.focus is None
        assert qml(root, scope + "Now").property("visible") is False
        _assert_focus_on_a_visible_page_item(scene)
        session.complete_homework(homework, False)
        settled(qapp, window)
        _run_out(qapp, window, root)
        session.complete_homework(homework, True)
        settled(qapp, window)


def test_start_again_on_the_now_card_starts_a_new_timer_on_the_same_homework_without_asking(
    qapp: QApplication, window: NativeWindow, keep_on_replace: None
) -> None:
    session = window.session
    root = show_material(qapp, window)
    bridge = root_bridge(root)
    asked: list[tuple[str, str]] = []
    session.focus_replace_needed.connect(lambda *names: asked.append(names))
    _run_out(qapp, window, root)
    before = dict(session.focus)
    bridge.showPage("day")
    pump(qapp)
    qml(root, "dayStartFocus").clicked.emit()
    pump(qapp)
    assert asked == []
    after = session.focus
    assert after["phase"] == "work" and after["running"] is True
    for key in ("assignmentId", "blockId", "title", "weekStart"):
        assert after[key] == before[key], key
    assert _card(root, "day")[1] != "Session finished"
    assert not session.assignments[before["assignmentId"]].get("completed")


def test_a_finished_quick_focus_is_named_quick_focus_and_has_no_mark_finished(
    qapp: QApplication, window: NativeWindow, keep_on_replace: None
) -> None:
    root = show_material(qapp, window)
    bridge = root_bridge(root)
    asked: list[tuple[str, str]] = []
    window.session.focus_replace_needed.connect(lambda *names: asked.append(names))
    _run_out(qapp, window, root, quick=True)
    for page, scope in (("myday", "myDay"), ("day", "day")):
        bridge.showPage(page)
        pump(qapp)
        assert _card(root, scope) == ("Quick focus", "Session finished", "Start again")
        assert qml(root, scope + "MarkFinished").property("visible") is False
    qml(root, "dayStartFocus").clicked.emit()
    pump(qapp)
    assert asked == []
    assert window.session.focus["title"] == "Quick focus"
    assert window.session.focus["phase"] == "work"


def test_clicking_the_now_cards_button_puts_keyboard_focus_on_it(
    qapp: QApplication, window: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A click on the card's button leaves keyboard focus on that button, so the screen or question it
    opens hands focus back to it, not to the rail button the student used before."""
    root = show_material(qapp, window)
    bridge = root_bridge(root)
    scene = window._material_page._quick.quickWindow()
    monkeypatch.setattr(window.session, "start_focus", lambda *_a, **_k: False)
    bridge.showPage("myday")
    pump(qapp)
    qml(root, "navDay").forceActiveFocus()
    pump(qapp)
    assert scene.activeFocusItem().objectName() == "navDay"
    button = qml(root, "myDayStartFocus")
    centre = button.mapToScene(QPointF(button.width() / 2, button.height() / 2)).toPoint()
    QTest.mouseClick(window._material_page._quick, Qt.MouseButton.LeftButton, pos=centre)
    pump(qapp)
    assert scene.activeFocusItem().objectName() == "myDayStartFocus"
