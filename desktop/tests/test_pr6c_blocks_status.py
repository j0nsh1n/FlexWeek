"""Tests for PR 6c: B3a3 class blocks, faded past days, status chips, disabled Plan, and screen contrast."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QUrl
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtQml import QQmlComponent
from PySide6.QtQuick import QQuickItem, QQuickView

from desktop.native.material.theme import (
    SIX_CLASSES,
    scheme,
    theme_object,
)
from desktop.native.tokens import contrast

QML_DIR = Path(__file__).resolve().parents[1] / "native" / "material" / "qml"
PURPLE_FAMILY = {"#eae6fa", "#2a244d", "#7c6cd6", "#9b8cf0"}


@pytest.fixture(scope="module")
def qapp() -> Iterator[QGuiApplication]:
    yield QGuiApplication.instance() or QGuiApplication(["test-pr6c"])


def _make_view(qapp: QGuiApplication) -> QQuickView:
    view = QQuickView()
    view.engine().addImportPath(str(QML_DIR))
    return view


def test_week_blocks_wear_their_class_colour_and_never_purple(qapp: QGuiApplication) -> None:
    """School, Sports, Activity, Homework, Study, Meals: bar/fill/title from class table, never purple."""
    categories_to_test = [
        ("School", "class", "class"),
        ("Sports", "exercise", "exercise"),
        ("Activity", "extra", "extra"),
        ("Homework", "assignments", "assignments"),
        ("Study", "study", "study"),
        ("Meals", "meals", "other"),
    ]
    for mode in ("light", "dark"):
        th = theme_object(scheme("Slate", mode, "std"), "comfortable", False, False)
        view = _make_view(qapp)
        comp = QQmlComponent(view.engine())
        comp.setData(
            b"import components 1.0\nEventBlock { width: 160; height: 48 }\n",
            view.engine().baseUrl(),
        )
        assert comp.isReady(), comp.errorString()

        for label, input_cat, expected_key in categories_to_test:
            item = comp.create()
            assert item is not None
            item.setProperty("theme", th)
            item.setProperty("category", input_cat)
            item.setProperty("title", f"{label} block")
            qapp.processEvents()

            shape = item.findChild(QQuickItem, "shape")
            bar = item.findChild(QQuickItem, "bar")
            title = item.findChild(QQuickItem, "title")

            expected_bar = th["classes"][expected_key]["bar"].lower()
            expected_fill = th["classes"][expected_key]["fill"].lower()
            expected_ink = th["classes"][expected_key]["ink"].lower()

            bar_col = QColor(bar.property("color")).name().lower()
            fill_col = QColor(shape.property("color")).name().lower()
            title_col = QColor(title.property("color")).name().lower()

            assert bar_col == expected_bar, f"{label} bar {bar_col} != {expected_bar}"
            assert fill_col == expected_fill, f"{label} fill {fill_col} != {expected_fill}"
            assert title_col == expected_ink, f"{label} title {title_col} != {expected_ink}"

            assert bar_col not in PURPLE_FAMILY, f"{label} bar {bar_col} is in the forbidden purple family"
            assert fill_col not in PURPLE_FAMILY, f"{label} fill {fill_col} is in the forbidden purple family"


def test_block_text_is_never_white_and_never_the_class_colour(qapp: QGuiApplication) -> None:
    """Block text is always ink (#0f172a / #ececec), never white, and never the class colour."""
    for mode in ("light", "dark"):
        th = theme_object(scheme("Slate", mode, "std"), "comfortable", False, False)
        view = _make_view(qapp)
        comp = QQmlComponent(view.engine())
        comp.setData(
            b"import components 1.0\nEventBlock { width: 160; height: 48 }\n",
            view.engine().baseUrl(),
        )
        for cat in SIX_CLASSES:
            for is_past in (False, True):
                item = comp.create()
                assert item is not None
                item.setProperty("theme", th)
                item.setProperty("category", cat)
                item.setProperty("past", is_past)
                item.setProperty("title", f"Test {cat}")
                item.setProperty("detail", "09:00 - 10:00")
                qapp.processEvents()

                bar = item.findChild(QQuickItem, "bar")
                title = item.findChild(QQuickItem, "title")
                detail = item.findChild(QQuickItem, "detail")

                bar_col = QColor(bar.property("color")).name().lower()
                title_col = QColor(title.property("color")).name().lower()
                detail_col = QColor(detail.property("color")).name().lower()

                assert title_col != "#ffffff", f"Title color cannot be white for {cat} in {mode}"
                assert title_col != bar_col, f"Title color cannot be bar color for {cat} in {mode}"
                assert detail_col != "#ffffff", f"Detail color cannot be white for {cat} in {mode}"
                assert detail_col != bar_col, f"Detail color cannot be bar color for {cat} in {mode}"


def test_a_past_block_fades_its_fill_and_bar_but_not_its_words(qapp: QGuiApplication) -> None:
    """When past: fill and bar fade (opacity 0.55), title and detail stay at opacity 1 in inkMuted."""
    for mode in ("light", "dark"):
        th = theme_object(scheme("Slate", mode, "std"), "comfortable", False, False)
        view = _make_view(qapp)
        comp = QQmlComponent(view.engine())
        comp.setData(
            b"import components 1.0\nEventBlock { width: 160; height: 48 }\n",
            view.engine().baseUrl(),
        )
        item = comp.create()
        assert item is not None
        item.setProperty("theme", th)
        item.setProperty("category", "class")
        item.setProperty("past", True)
        item.setProperty("title", "Past Class")
        item.setProperty("detail", "Yesterday")
        qapp.processEvents()

        shape = item.findChild(QQuickItem, "shape")
        bar = item.findChild(QQuickItem, "bar")
        title = item.findChild(QQuickItem, "title")
        detail = item.findChild(QQuickItem, "detail")

        # Root item maintains full opacity (not dimmed at root level)
        assert item.property("opacity") == pytest.approx(1.0)
        # Shape and bar fade to 0.55
        assert shape.property("opacity") == pytest.approx(0.55)
        assert bar.property("opacity") == pytest.approx(0.55)
        # Words keep full opacity (1.0)
        assert title.property("opacity") == pytest.approx(1.0)
        assert detail.property("opacity") == pytest.approx(1.0)

        # Word color is inkMuted
        expected_muted = th["inkMuted"].lower()
        assert QColor(title.property("color")).name().lower() == expected_muted
        assert QColor(detail.property("color")).name().lower() == expected_muted


def test_drawn_block_text_reaches_4_5_to_1(qapp: QGuiApplication) -> None:
    """Offscreen Week frame grab: text >= 4.5:1 on fill for past/current; bar >= 3:1 on card/page."""
    # Week columns are the page colour and today's column the card colour; a past block fades over either.
    grounds = [(mode, ground) for mode in ("light", "dark") for ground in ("card", "page")]
    for mode, ground in grounds:
        th = theme_object(scheme("Slate", mode, "std"), "comfortable", False, False)
        view = _make_view(qapp)
        view.resize(1000, 800)

        qml_source = f"""
import QtQuick
import components 1.0

Rectangle {{
    width: 1000
    height: 800
    color: "{th[ground]}"
    Column {{
        id: col
        objectName: "col"
        x: 40
        y: 40
        spacing: 12
        Repeater {{
            model: 12
            EventBlock {{
                width: 200
                height: 48
                theme: parent.parent.theme
                category: ["class", "exercise", "extra", "assignments", "study", "other"][index % 6]
                past: index >= 6
                title: "Sample " + category
                detail: "09:00 - 10:00"
            }}
        }}
    }}
    property var theme
}}
"""
        comp = QQmlComponent(view.engine())
        comp.setData(qml_source.encode("utf-8"), view.engine().baseUrl())
        root = comp.create()
        assert root is not None, comp.errorString()
        root.setProperty("theme", th)
        view.setContent(QUrl(), comp, root)
        view.show()
        qapp.processEvents()

        img = view.grabWindow()
        view.hide()
        view.deleteLater()
        col = root.findChild(QQuickItem, "col")
        blocks = [child for child in col.childItems() if child.property("category") is not None]
        assert len(blocks) == 12

        for child in blocks:
            pt = child.mapToScene(QPointF(0, 0))
            cx, cy = int(pt.x()), int(pt.y())
            # The fill at the block's lower right corner, clear of the bar, the title and the detail.
            right = cx + int(child.width()) - 8
            low = cy + int(child.height()) - 4
            fill_px = img.pixelColor(right, low).name()
            # Read bar pixel
            bar_px = img.pixelColor(cx + 2, cy + 10).name()
            # Read card pixel next to the block
            card_px = img.pixelColor(cx - 5, cy + 10).name()

            title_item = child.findChild(QQuickItem, "title")
            title_col = title_item.property("color").name()

            cat = str(child.property("category"))
            past = bool(child.property("past"))

            # Title contrast on fill >= 4.5:1
            c_text = contrast(title_col, fill_px)
            where = f"{cat} (past={past}) in {mode} on {ground}"
            assert c_text >= 4.5, f"Text contrast {c_text:.2f} < 4.5:1 for {where}"

            # Bars reach 3:1 on the card (spec) and on the page (Sports was darkened for it).
            if not past:
                c_bar = contrast(bar_px, card_px)
                assert c_bar >= 3.0, f"Bar contrast {c_bar:.2f} < 3:1 for {cat} in {mode} on {ground}"

        view.hide()
        qapp.processEvents()


def test_status_chips_have_an_icon_and_a_word_on_a_tint(qapp: QGuiApplication) -> None:
    """Tag status chips: icon visible, word present, fill is tint, radius is pill (height / 2)."""
    kind_specs = [
        ("plenty", "statusDoneTint", "statusDone", "check"),
        ("tight", "statusDueSoonTint", "statusDueSoon", "schedule"),
        ("cutting", "statusOverdueTint", "statusOverdue", "warning"),
    ]
    for mode in ("light", "dark"):
        th = theme_object(scheme("Slate", mode, "std"), "comfortable", False, False)
        view = _make_view(qapp)
        comp = QQmlComponent(view.engine())
        comp.setData(
            b"import components 1.0\nTag { width: 100; height: 20 }\n",
            view.engine().baseUrl(),
        )
        assert comp.isReady(), comp.errorString()

        for kind, expected_tint_key, expected_status_key, expected_icon in kind_specs:
            tag = comp.create()
            assert tag is not None
            tag.setProperty("theme", th)
            tag.setProperty("kind", kind)
            tag.setProperty("text", f"Status {kind}")
            qapp.processEvents()

            shape = tag.findChild(QQuickItem, "shape")
            icon = tag.findChild(QQuickItem, "icon")
            label = tag.findChild(QQuickItem, "label")

            assert shape is not None
            assert icon is not None
            assert label is not None

            # Pill radius = height / 2
            assert shape.property("radius") == pytest.approx(tag.property("height") / 2)

            # Icon is visible with correct icon name
            assert icon.property("visible") is True
            assert icon.property("name") == expected_icon

            # Word is present
            assert label.property("text") == f"Status {kind}"

            # Fill matches the status tint
            expected_fill = th[expected_tint_key].lower()
            expected_ink = th[expected_status_key].lower()
            actual_fill = QColor(shape.property("color")).name().lower()
            actual_ink = QColor(label.property("color")).name().lower()

            assert actual_fill == expected_fill, f"{kind} fill in {mode} expected {expected_fill}"
            assert actual_ink == expected_ink, f"{kind} ink in {mode} expected {expected_ink}"

            # Contrast between word and tint >= 4.5:1
            assert contrast(actual_ink, actual_fill) >= 4.5

        # Plain tag keeps neutral look
        plain_tag = comp.create()
        assert plain_tag is not None
        plain_tag.setProperty("theme", th)
        plain_tag.setProperty("kind", "plain")
        plain_tag.setProperty("text", "Plain text")
        qapp.processEvents()

        plain_shape = plain_tag.findChild(QQuickItem, "shape")
        plain_icon = plain_tag.findChild(QQuickItem, "icon")
        assert plain_shape.property("radius") == pytest.approx(plain_tag.property("height") / 2)
        assert plain_icon.property("visible") is False or plain_icon.property("name") == ""


def test_disabled_plan_is_a_text_button_with_its_hint(qapp: QGuiApplication) -> None:
    """When enabled false (count == 0), Plan is a text button and hint stays under it."""
    for mode in ("light", "dark"):
        th = theme_object(scheme("Slate", mode, "std"), "comfortable", False, False)
        view = _make_view(qapp)
        drawer_qml = QML_DIR / "week" / "HomeworkDrawer.qml"
        comp = QQmlComponent(view.engine(), QUrl.fromLocalFile(str(drawer_qml)))
        assert comp.isReady(), comp.errorString()

        drawer = comp.create()
        assert drawer is not None
        drawer.setProperty("theme", th)
        drawer.setProperty("count", 0)
        qapp.processEvents()

        plan = drawer.findChild(QQuickItem, "planHomework")
        assert plan is not None
        assert plan.property("enabled") is False
        assert plan.property("kind") == "text"

        empty_box = drawer.findChild(QQuickItem, "homeworkEmpty")
        empty_text = drawer.findChild(QQuickItem, "homeworkEmptyText")
        assert empty_box is not None
        assert empty_text is not None
        assert empty_box.property("visible") is True
        assert empty_text.property("text") == "Everything has a time."

        # Hint text color is inkMuted
        expected_muted = th["inkMuted"].lower()
        actual_muted = QColor(empty_text.property("color")).name().lower()
        assert actual_muted == expected_muted
        # Plan's own words and icon are the muted ink at full opacity, not the 38 % disabled ink (Sol, PR 6c).
        ink = QColor(plan.property("ink"))
        assert ink.name().lower() == expected_muted and ink.alphaF() == 1.0
        label = plan.findChild(QQuickItem, "label")
        assert QColor(label.property("color")).name().lower() == expected_muted
        assert QColor(label.property("color")).alphaF() == 1.0


def test_a_short_block_keeps_its_words_inside(qapp: QGuiApplication) -> None:
    """A 30-minute block is 36 px tall: a two-line title and its time must not paint into the next hour."""
    th = theme_object(scheme("Slate", "light", "std"), "comfortable", False, False)
    view = _make_view(qapp)
    comp = QQmlComponent(view.engine())
    comp.setData(
        b"import components 1.0\nEventBlock { width: 90; height: 36; category: 'class'; "
        b"title: 'Chemistry lab report write-up'; detail: '8:00-8:30 AM' }\n",
        view.engine().baseUrl(),
    )
    block = comp.create()
    assert block is not None, comp.errorString()
    block.setProperty("theme", th)
    qapp.processEvents()
    words = block.findChild(QQuickItem, "words")
    title = block.findChild(QQuickItem, "title")
    detail = block.findChild(QQuickItem, "detail")
    tall = float(title.property("implicitHeight")) + float(detail.property("implicitHeight")) + 6
    assert tall > block.height(), "the sample must overflow, or it tests nothing"
    assert words.property("clip") is True
    assert words.width() == block.width() and words.height() == block.height()
    block.deleteLater()
    view.deleteLater()
    qapp.processEvents()

