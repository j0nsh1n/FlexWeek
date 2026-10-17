"""The rail, plan result and unfinished homework fit at the smallest supported window."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from desktop.native.layouts.registry import sanitize_layout
from desktop.native.look import sanitize_look
from desktop.native.window import NativeWindow
from desktop.tests.window_support import (  # noqa: F401
    qapp,
    server,
    settled,
    signed_out,
    window,
)

SMALL_WINDOW = (1024, 640)  # The brief's smallest supported window.
NORMAL_WINDOW = (1280, 800)  # The brief's normal-size layout guard.
EVENT_PASSES = 10  # Let the real window settle after each size or appearance change.
LINE_CENTER_TOLERANCE = 4  # The normal-size guard allows small font-metric rounding differences.
HOMEWORK_DAY = 1  # The seeded focus work is Tuesday, after the held Monday clock.
PLAN_DEADLINE_HOUR = 8  # The plan fixture is due before the week can fit any work.
HOMEWORK_MINUTES = 60  # Each rail item is one hour, matching its displayed session length.
POSTER_MINUTES = 600  # Ten hours ensures the solver reports the plan result actions.
OVERDUE_MINUTES = 180  # Three hours gives the unfinished row enough words to wrap.


def show_large_classic(qapp, window: NativeWindow, width: int, height: int) -> None:  # noqa: F811
    window._look = sanitize_look({"preset": "default", "knobs": {"text": "large"}})
    window.session.look = window._look
    window._carry_look()
    window._layout = sanitize_layout({"main": "classic", "day": "one", "options": {}})
    window._apply_appearance()
    window._on_week()
    window.resize(width, height)
    window.show()
    for _ in range(EVENT_PASSES):
        qapp.processEvents()


def visible_controls(widget: QWidget) -> list[QWidget]:
    return [
        child
        for child in widget.findChildren(QWidget)
        if isinstance(child, (QPushButton, QLabel)) and child.isVisibleTo(widget)
    ]


def assert_controls_fit_without_overlap(widget: QWidget) -> None:
    controls = visible_controls(widget)
    for control in controls:
        if isinstance(control, QPushButton):
            assert control.width() >= control.sizeHint().width(), (
                f"{control.text()!r} is cut: {control.width()} < {control.sizeHint().width()}"
            )
    rects = [QRect(control.mapTo(widget, QPoint(0, 0)), control.size()) for control in controls]
    for index, first in enumerate(controls):
        for second, second_rect in zip(controls[index + 1 :], rects[index + 1 :], strict=True):
            first_rect = rects[index]
            assert not first_rect.intersects(second_rect), (
                f"{first.objectName() or first.text()!r} overlaps "
                f"{second.objectName() or second.text()!r}"
            )


def assert_plan_buttons_in_order(review: QWidget) -> None:
    """Details on the left, then Replan all my homework, then Got it, wherever the buttons sit."""
    names = ("planReviewDetails", "planReviewReplan", "planReviewDismiss")
    found = [review.findChild(QPushButton, name) for name in names]
    assert all(button is not None for button in found), "plan result buttons are present"
    lefts = [button.mapTo(review, QPoint(0, 0)).x() for button in found]
    assert lefts == sorted(lefts), f"plan result buttons read Details, Replan, Got it; lefts were {lefts}"


def test_rail_next_rows_put_start_focus_below_the_words_at_1024_large(
    qapp,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    session = window.session
    monday = datetime.fromisoformat(session.week_start)
    session.now_ms = lambda: int(
        (monday + timedelta(days=HOMEWORK_DAY, hours=PLAN_DEADLINE_HOUR)).timestamp() * 1000
    )
    session.add_homework(
        {
            "id": "history", "title": "History essay",
            "due": (monday + timedelta(days=HOMEWORK_DAY)).strftime("%Y-%m-%dT23:59"),
            "estimate_min": HOMEWORK_MINUTES, "revision": 0,
        }
    )
    session.add_homework(
        {
            "id": "biology", "title": "Biology lab report",
            "due": (monday + timedelta(days=HOMEWORK_DAY)).strftime("%Y-%m-%dT23:59"),
            "estimate_min": HOMEWORK_MINUTES, "revision": 0,
        }
    )
    session.save()
    settled(qapp, window)
    for key, start in (("history", "09:00"), ("biology", "10:00")):
        block = next(item for item in session.blocks if item.get("assignment_id") == key)
        session.add_block({**block, "start": start, "days": [HOMEWORK_DAY], "pinned": True})
    session.save()
    settled(qapp, window)
    show_large_classic(qapp, window, *SMALL_WINDOW)
    rows = window.rail.next.rest.findChildren(QWidget, "railNextRow")
    assert rows, "homework later today appears under Next"
    for row in rows:
        words = row.findChildren(QLabel)
        focus = row.findChild(QPushButton, "railNextRowFocus")
        assert focus is not None, "homework row has Start focus"
        assert focus.mapTo(row, QPoint(0, 0)).y() >= max(
            label.mapTo(row, QPoint(0, label.height())).y() for label in words
        ), "Start focus sits below the name and time"
        assert_controls_fit_without_overlap(row)
    card = window.rail.next.card
    assert_controls_fit_without_overlap(card)
    card_focus = window.rail.next.start_focus
    assert card_focus.width() >= card_focus.sizeHint().width(), "Next card Start focus is whole"
    assert card_focus.mapTo(window.rail.next.card, QPoint(0, 0)).y() >= max(
        label.mapTo(window.rail.next.card, QPoint(0, label.height())).y()
        for label in window.rail.next.card.findChildren(QLabel)
    ), "Next card Start focus sits below its words"


def test_plan_result_wraps_buttons_below_heading_at_1024_large(
    qapp,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    session = window.session
    monday = date.fromisoformat(session.week_start)
    session.add_homework(
        {
            "id": "poster", "title": "Science fair poster",
            "due": f"{monday.isoformat()}T{PLAN_DEADLINE_HOUR:02d}:00",
            "estimate_min": POSTER_MINUTES, "revision": 0,
        }
    )
    session.save()
    settled(qapp, window)
    session.solve()
    settled(qapp, window)
    show_large_classic(qapp, window, *SMALL_WINDOW)
    assert window.plan_review.isVisible(), "the plan result is present"
    qapp.processEvents()
    assert_controls_fit_without_overlap(window.plan_review)
    heading = window.plan_review.heading
    buttons = [
        window.plan_review.findChild(QPushButton, "planReviewDetails"),
        window.plan_review.findChild(QPushButton, "planReviewReplan"),
        window.plan_review.findChild(QPushButton, "planReviewDismiss"),
    ]
    assert all(button is not None for button in buttons), "plan result buttons are present"
    heading_bottom = heading.mapTo(window.plan_review, QPoint(0, heading.height())).y()
    assert all(button.mapTo(window.plan_review, QPoint(0, 0)).y() >= heading_bottom for button in buttons), (
        "plan result buttons sit below its heading when the row does not fit"
    )
    assert_plan_buttons_in_order(window.plan_review)


def test_plan_result_stays_on_one_line_at_1280_normal(
    qapp,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    session = window.session
    monday = date.fromisoformat(session.week_start)
    session.add_homework(
        {
            "id": "poster", "title": "Science fair poster",
            "due": f"{monday.isoformat()}T{PLAN_DEADLINE_HOUR:02d}:00",
            "estimate_min": POSTER_MINUTES, "revision": 0,
        }
    )
    session.save()
    settled(qapp, window)
    session.solve()
    settled(qapp, window)
    window.resize(*NORMAL_WINDOW)
    window._look = sanitize_look({"preset": "default", "knobs": {"text": "normal"}})
    window.session.look = window._look
    window._carry_look()
    window._apply_appearance()
    for _ in range(EVENT_PASSES):
        qapp.processEvents()
    heading = window.plan_review.heading
    for name in ("planReviewDetails", "planReviewReplan", "planReviewDismiss"):
        button = window.plan_review.findChild(QPushButton, name)
        assert button is not None and abs(
            button.geometry().center().y() - heading.geometry().center().y()
        ) <= LINE_CENTER_TOLERANCE, f"{name} shares the heading line at 1280x800 Normal"
    assert_plan_buttons_in_order(window.plan_review)


def test_plan_result_returns_to_one_line_after_a_small_window(
    qapp,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    session = window.session
    monday = date.fromisoformat(session.week_start)
    session.add_homework(
        {
            "id": "poster", "title": "Science fair poster",
            "due": f"{monday.isoformat()}T{PLAN_DEADLINE_HOUR:02d}:00",
            "estimate_min": POSTER_MINUTES, "revision": 0,
        }
    )
    session.save()
    settled(qapp, window)
    session.solve()
    settled(qapp, window)
    show_large_classic(qapp, window, *SMALL_WINDOW)
    review = window.plan_review
    details = review.findChild(QPushButton, "planReviewDetails")
    assert details is not None and details.mapTo(review, QPoint(0, 0)).y() > 0, "small: buttons moved down"
    window.setMinimumSize(0, 0)
    window.resize(*NORMAL_WINDOW)
    window._look = sanitize_look({"preset": "default", "knobs": {"text": "normal"}})
    window.session.look = window._look
    window._carry_look()
    window._apply_appearance()
    for _ in range(EVENT_PASSES):
        qapp.processEvents()
    heading = review.heading
    for name in ("planReviewDetails", "planReviewReplan", "planReviewDismiss"):
        button = review.findChild(QPushButton, name)
        assert button is not None and abs(
            button.geometry().center().y() - heading.geometry().center().y()
        ) <= LINE_CENTER_TOLERANCE, f"{name} is back on the heading line at 1280x800 Normal"
    assert_plan_buttons_in_order(review)


def test_unfinished_rows_wrap_without_horizontal_scrolling_at_1024_large(
    qapp,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    # A week with something in it, so the week grid and the rail beside it are on screen as for a student:
    # on the empty-week page the rail is hidden and the card had the window's whole width.
    window.session.add_block(
        {"id": "school", "title": "School", "kind": "locked", "category": "school",
         "start": "08:00", "duration_min": 390, "days": [0, 1, 2, 3, 4]}
    )
    window.session.save()
    settled(qapp, window)
    show_large_classic(qapp, window, *SMALL_WINDOW)
    assert window.rail.isVisible(), "the rail is beside the week, as a student sees it at 1024x640"
    panel = window.unfinished_panel
    panel.set_items(
        [{"id": "bio", "title": "Biology lab report with an extended title", "remaining_min": OVERDUE_MINUTES,
          "due": "2026-10-12T23:59", "left_over_state": "overdue", "plannable": True}]
    )
    for _ in range(EVENT_PASSES):
        qapp.processEvents()
    assert panel.isVisibleTo(window), "overdue homework is displayed"
    assert not panel.list.horizontalScrollBar().isVisible(), "unfinished homework does not scroll sideways"
    assert panel.list.horizontalScrollBar().maximum() == 0, "unfinished homework has no horizontal range"
    row = panel.list.itemWidget(panel.list.item(0))
    assert row is not None
    assert row.findChild(QLabel, "unfinishedRow").wordWrap(), "unfinished homework words wrap"
    assert_controls_fit_without_overlap(panel)
    # A hidden scroll bar does not make a row fit: what is past the list's edge is simply not drawn.
    viewport = panel.list.viewport()
    for control in (row, *visible_controls(row)):
        right = control.mapTo(viewport, QPoint(control.width(), 0)).x()
        assert right <= viewport.width(), (
            f"{control.objectName() or type(control).__name__} ends at {right}, past the list's edge at "
            f"{viewport.width()}"
        )


def test_unfinished_rows_keep_buttons_on_the_text_line_at_1280_normal(
    qapp,  # noqa: F811
    window: NativeWindow,  # noqa: F811
) -> None:
    window.resize(*NORMAL_WINDOW)
    window._look = sanitize_look({"preset": "default", "knobs": {"text": "normal"}})
    window.session.look = window._look
    window._carry_look()
    window._apply_appearance()
    panel = window.unfinished_panel
    panel.set_items(
        [{"id": "bio", "title": "Biology", "remaining_min": HOMEWORK_MINUTES, "due": "2026-10-12T23:59",
          "left_over_state": "overdue", "plannable": True}]
    )
    for _ in range(EVENT_PASSES):
        qapp.processEvents()
    row = panel.list.itemWidget(panel.list.item(0))
    text = row.findChild(QLabel, "unfinishedRow")
    for button in row.findChildren(QPushButton):
        assert abs(button.geometry().center().y() - text.geometry().center().y()) <= LINE_CENTER_TOLERANCE, (
            f"{button.text()} shares the homework text line at 1280x800 Normal"
        )
