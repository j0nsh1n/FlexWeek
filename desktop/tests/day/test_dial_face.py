"""Day dial's face: what a click on it reaches, what it says to a screen reader, which words it plans
to write along its arcs, and how its hand moves. Where the ring, hand and words are drawn is judged on
the pictures (desktop/tests/pictures/_day_g02.py)."""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Iterator
from dataclasses import replace

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from desktop.native.layouts.dial import HAND_MS
    from desktop.native.motion import apply_ui_effects, duration
    from desktop.native.weekmodel import clock_label, minute_of, set_clock_24h
    from desktop.tests.day.support_dial import arc_words, face, on_ring, reachable, row_buttons, shown
    from desktop.tests.motion_support import ManualTime, manual_time  # noqa: F401
    from desktop.tests.test_weekmodel import BLOCKS, block


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication(["flexweek-dial-face-test"])
    yield application


def test_every_segment_has_a_row_a_keyboard_can_reach(qapp: QApplication) -> None:
    view = shown(qapp, "19:00")
    opened: list[str] = []
    view.block_activated.connect(opened.append)
    for item in row_buttons(view):
        assert item.focusPolicy() != Qt.FocusPolicy.NoFocus
        item.click()
    assert opened == ["school", "dinner", "essay-1", "chem-1"]
    assert reachable(face(view)) == set(opened)


def test_a_click_on_a_segment_opens_that_block_and_the_middle_opens_nothing(qapp: QApplication) -> None:
    view = shown(qapp, "19:00")
    dial = face(view)
    opened: list[str] = []
    view.block_activated.connect(opened.append)
    QTest.mouseClick(dial, Qt.MouseButton.LeftButton, pos=QPoint(dial.width() // 2, dial.height() // 2))
    assert opened == []
    QTest.mouseClick(dial, Qt.MouseButton.LeftButton, pos=on_ring(dial, 20 * 60 + 45).toPoint())
    assert opened == ["chem-1"]


def test_homework_inside_a_fixed_block_can_still_be_clicked(qapp: QApplication) -> None:
    inside = [*BLOCKS, block("study-hall", "flexible", [3], "10:00", 45, assignment_id="essay")]
    dial = face(shown(qapp, "19:00", inside))
    assert dial.block_at(on_ring(dial, 10 * 60 + 20)).block_id == "study-hall"
    assert dial.block_at(on_ring(dial, 9 * 60)).block_id == "school"
    assert dial.block_at(on_ring(dial, 12 * 60)).block_id == "school"


def test_the_ring_is_the_whole_day_so_a_block_at_dawn_and_one_at_night_can_be_clicked(
    qapp: QApplication,
) -> None:
    early = [
        *BLOCKS,
        block("paper-round", "locked", [3], "05:00", 45),
        block("late-call", "locked", [3], "23:00", 30),
    ]
    assert {"paper-round", "late-call"} <= reachable(face(shown(qapp, "19:00", early)))


def test_the_face_says_the_time_and_the_free_time_left(qapp: QApplication) -> None:
    assert face(shown(qapp, "15:40")).accessibleDescription() == "15:40. 3 h 20 min free until 22:00"
    assert face(shown(qapp, "19:00")).accessibleDescription() == "19:00. 45 min free until 22:00"
    assert face(shown(qapp, "22:30")).accessibleDescription() == "22:30"


def test_the_face_is_described_for_a_screen_reader(qapp: QApplication) -> None:
    dial = face(shown(qapp, "19:00"))
    assert dial.accessibleName() == "Thursday: School 08:00, Dinner 18:00, Essay-1 18:45, Chem-1 20:00"


def test_names_are_planned_along_the_arcs_that_fit_and_left_off_the_ones_that_do_not(
    qapp: QApplication,
) -> None:
    """The arcs carried no words once. School's arc is wide enough for its name; Dinner's is half an
    hour, which the name would run off, so it is left off and the list beside the face says it."""
    words = arc_words(shown(qapp, "13:40"))
    assert "School" in words
    assert "Dinner" not in words
    assert "Earlier today" in words, "free time already gone"
    # A free stretch that does fit keeps its words: School alone leaves the rest of the day free.
    only_school = [block("school", "locked", [3], "08:00", 390)]
    assert "Free until 22:00" in arc_words(shown(qapp, "13:40", only_school)), "free time still ahead"


def test_a_ring_too_thin_for_words_or_a_day_without_a_now_writes_less(qapp: QApplication) -> None:
    small = shown(qapp, "13:40")
    small.resize(700, 420)
    qapp.processEvents()
    assert arc_words(small) == [], "a ring thinner than the words are tall is left bare"
    # Another week has no now, so no free time is said to be gone or ahead.
    other = shown(qapp, "13:40", today=None)
    assert [words for words in arc_words(other) if words.startswith(("Earlier", "Free"))] == []
    assert "School" in arc_words(other)


def test_free_until_follows_the_clock_setting(qapp: QApplication) -> None:
    set_clock_24h(False)
    wanted = f"Free until {clock_label(22 * 60)}"
    assert "PM" in wanted
    assert wanted in arc_words(shown(qapp, "13:40", []))
    set_clock_24h(True)
    assert "Free until 22:00" in arc_words(shown(qapp, "13:40", []))


@pytest.mark.parametrize(("level", "eases"), [("normal", True), ("reduce", False), ("off", False)])
def test_the_hand_eases_to_where_the_time_moved_it_and_jumps_where_nothing_may_travel(
    qapp: QApplication, manual_time: ManualTime, level: str, eases: bool
) -> None:
    """The hand eases for 240 ms as the mock-up's does, within the animation levels. It is read as the
    minute it points at: None once it is simply at now."""
    apply_ui_effects(level)
    try:
        view = shown(qapp, "13:40")
        view.show_week(replace(view.scene, minute=minute_of("15:10")))
        hand = face(view)
        if not eases:
            assert hand._hand_at is None, "the hand is at the new minute at once"
            return
        assert hand._hand_at == pytest.approx(minute_of("13:40")), "it leaves from where it was"
        manual_time.advance(duration(HAND_MS) // 2)
        assert minute_of("13:40") < hand._hand_at < minute_of("15:10"), "and is on its way"
        manual_time.advance(duration(HAND_MS))
        assert hand._hand_at is None, "and arrives"
    finally:
        apply_ui_effects("normal")
