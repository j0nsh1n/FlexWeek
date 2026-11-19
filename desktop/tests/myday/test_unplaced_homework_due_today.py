# ruff: noqa: F811
"""Homework due tonight that has no time yet is named on the Material week and on My day, and neither says
the day is free."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from backend.tests.fake_clock import CLOCK  # noqa: E402
from desktop.native.weekmodel import build_week  # noqa: E402
from desktop.tests.day.support_layouts_window import thursday_at  # noqa: E402
from desktop.tests.material_support import pump  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.week.support_material import (  # noqa: E402
    _qml,
    _repeater_texts,
    _show_material,
    material_window,  # noqa: F401
)
from desktop.tests.window_support import qapp, settled  # noqa: E402,F401

FREE_TODAY = (
    "done for today",
    "nothing else today",
    "all clear",
    "the rest of the day is yours",
    "a free day",
    "0 min left today",
    "nothing on this day",
    "no homework tonight",
    "everything has a time",
)


def _math_due_tonight(qapp, window) -> None:
    """Math worksheet due tonight with no time; the essay's placed time is gone."""
    session = window.session
    CLOCK.set(thursday_at(window, 16))
    session.blocks = [item for item in session.blocks if item.get("assignment_id") != "essay"]
    session._touch("clearing the placed essay")
    due = f"{thursday_at(window, 0).date().isoformat()}T21:00"
    session.add_homework(
        {"id": "math", "title": "Math worksheet", "due": due, "estimate_min": 45, "revision": 0}
    )
    session.save()
    settled(qapp, window)


def test_the_shared_empty_day_words_name_the_homework_and_never_say_the_day_is_free(qapp, window) -> None:
    _math_due_tonight(qapp, window)
    session = window.session
    model = build_week(session.week_start, session.blocks, session.assignments, session.trace)
    today = session.today_column(thursday_at(window, 0).date().isoformat())
    assert [item.title for item in model.due_today_unplaced(today)] == ["Math worksheet"]
    kicker, title, line = model.leftover_parts(today)
    said = f"{kicker} {title} {line}".lower()
    assert title == "Math worksheet", said
    for phrase in FREE_TODAY:
        assert phrase not in said, f"{phrase!r} in {said!r}"


def test_the_material_week_lists_it_and_does_not_say_everything_has_a_time(qapp, window) -> None:
    _math_due_tonight(qapp, window)
    root = _show_material(qapp, window)
    window._material_page.publish()
    wait_until(qapp, lambda: "Math worksheet" in _repeater_texts(root, "homeworkRows", "homeworkTitle"))
    assert _qml(root, "homeworkEmpty").property("visible") is False
    # The essay lost its time in the setup, so it waits too.
    assert _qml(root, "homeworkCount").property("text") == "2"


@pytest.mark.xfail(
    strict=True,
    reason="product gap: Material's My day card and ring read only placed blocks, so homework due tonight "
    "with no time is not named there (the shared words name it; the Widgets screens read them)",
)
def test_material_my_day_names_it_in_the_card_and_never_says_the_day_is_free(qapp, window) -> None:
    _math_due_tonight(qapp, window)
    root = _show_material(qapp, window)
    myday = root.property("bridge").property("myday")
    pump(qapp, 10)
    said = " ".join(
        str(myday.property(name)) for name in ("nowTitle", "nowLine", "ringCaption")
    ).lower()
    assert "math worksheet" in said, said
    for phrase in FREE_TODAY:
        assert phrase not in said, f"{phrase!r} in {said!r}"
