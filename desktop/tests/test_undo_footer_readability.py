"""Regression tests for W5: Undo toast footer readability in Bento layout.

Ensures settled Undo toast does not obscure the 'Not placed yet' instruction
(bentoWaitingHint) or other footer text in BentoView.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QRegion
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QScrollArea, QVBoxLayout, QWidget

from desktop.native.fonts import load_fonts
from desktop.native.look import pack_stylesheet
from desktop.native.widgets import Toast, use_app_style
from desktop.tests.test_layout_bento import shown


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance() or QApplication(["flexweek-w5-test"])
    load_fonts()
    use_app_style(app)
    return app


def _text_ink_in_host(label: QLabel, host: QWidget) -> QRectF:
    """Return painted text bounds of label in host coordinates."""
    flags = int(label.alignment())
    if label.wordWrap():
        flags |= int(Qt.TextFlag.TextWordWrap)
    ink = label.fontMetrics().boundingRect(label.rect(), flags, label.text())
    ink.translate(label.mapTo(host, QPoint(0, 0)))
    return QRectF(ink)


def _toast_card_in_host(toast: Toast, host: QWidget) -> QRectF:
    """Return toast card bounding rectangle in host coordinates."""
    return QRectF(toast.card.mapTo(host, QPoint(0, 0)), toast.card.size())


def _visible_text_ink_in_host(label: QLabel, host: QWidget) -> QRegion:
    """Clip ink to its ancestors, without hiding a collision behind the toast."""
    if not label.isVisible():
        return QRegion()
    ink = QRegion(_text_ink_in_host(label, host).toAlignedRect())
    ancestor: QWidget | None = label
    while ancestor is not None:
        bounds = ancestor.rect().translated(ancestor.mapTo(host, QPoint()))
        ink &= QRegion(bounds)
        if ancestor is host:
            return ink
        ancestor = ancestor.parentWidget()
    raise AssertionError("The label must belong to the inspected host")


def test_partial_clipping_does_not_report_invisible_text_as_a_collision(qapp: QApplication) -> None:
    host = QWidget()
    try:
        host.resize(240, 240)
        scroll = QScrollArea(host)
        scroll.setGeometry(10, 10, 180, 50)
        body = QWidget()
        body.resize(160, 220)
        label = QLabel("Drag one onto the week. " * 5, body)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        label.setGeometry(0, 0, 140, 180)
        scroll.setWidget(body)
        host.show()
        qapp.processEvents()
        ink = _text_ink_in_host(label, host)
        viewport = QRectF(scroll.viewport().mapTo(host, QPoint()), scroll.viewport().size())
        outside_card = QRectF(ink.left(), viewport.bottom() + 3, ink.width(), 20)
        visible = _visible_text_ink_in_host(label, host)
        assert not visible.isEmpty(), "The control must be partially visible"
        assert outside_card.intersects(ink), "The old oracle must report a false collision"
        assert not visible.intersects(outside_card.toAlignedRect())
        inside_card = QRectF(ink.left(), viewport.top(), ink.width(), 15)
        assert visible.intersects(inside_card.toAlignedRect()), "Real visible overlap must still fail"
    finally:
        host.close()
        host.deleteLater()
        qapp.processEvents()


def test_settled_undo_toast_does_not_obscure_bento_waiting_instruction(qapp: QApplication) -> None:
    """W5: Settled Undo toast at 1280x820 must not obscure bentoWaitingHint ink.

    Fails old geometry where bentoWaitingHint sat at the bottom of bentoWaiting
    (after box.addStretch(1)), intersecting the settled toast card at y in [753, 804].
    """
    host = QWidget()
    try:
        host.resize(1280, 820)
        host.setStyleSheet(pack_stylesheet("light-frost", False, None))
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        view = shown(qapp, size=(1280, 820))
        layout.addWidget(view)
        host.show()
        QTest.qWait(850)

        toast = Toast(host, view)
        toast.show_message("Moved block", "Undo")
        QTest.qWait(1200)
        qapp.processEvents()

        hint = view.findChild(QLabel, "bentoWaitingHint")
        assert hint is not None and hint.isVisible(), "bentoWaitingHint must be visible"
        assert hint.text() == "Drag one onto the week."

        card = _toast_card_in_host(toast, host)
        ink = _text_ink_in_host(hint, host)

        # Prove footer text paint bounds are unobscured while settled toast visible
        assert not _visible_text_ink_in_host(hint, host).intersects(card.toAlignedRect()), (
            f"Settled toast card {card.getRect()} collides with bentoWaitingHint ink {ink.getRect()}"
        )
        # Hint must sit clearly above the toast card
        assert ink.bottom() < card.top(), f"Expected ink.bottom {ink.bottom()} < card.top {card.top()}"
    finally:
        host.close()
        host.deleteLater()
        qapp.processEvents()


@pytest.mark.parametrize("size", [(1280, 800), (1280, 820), (1024, 740)])
@pytest.mark.parametrize("scale", [1.0, 1.2])
def test_undo_toast_readability_across_sizes_and_scales(
    qapp: QApplication, size: tuple[int, int], scale: float
) -> None:
    """Verify bentoWaitingHint paint bounds remain unobscured across normal and large scales."""
    host = QWidget()
    try:
        host.resize(*size)
        host.setStyleSheet(pack_stylesheet("light-frost", False, None))
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        view = shown(qapp, size=size, scale=scale)
        layout.addWidget(view)
        host.show()
        QTest.qWait(400)

        toast = Toast(host, view)
        toast.show_message("Moved History essay to Fri 18:00.", "Undo")
        QTest.qWait(1200)
        qapp.processEvents()

        hint = view.findChild(QLabel, "bentoWaitingHint")
        assert hint is not None and hint.isVisible()

        card = _toast_card_in_host(toast, host)
        ink = _text_ink_in_host(hint, host)

        assert not _visible_text_ink_in_host(hint, host).intersects(card.toAlignedRect()), (
            f"size={size} scale={scale}: card {card.getRect()} collides with hint {ink.getRect()}"
        )
    finally:
        host.close()
        host.deleteLater()
        qapp.processEvents()


def test_cramped_1024x740_scroll_bottom_reach_unobscured(qapp: QApplication) -> None:
    """At 1024x740 cramped mode, scrolling to maximum bottom must not collide with toast."""
    host = QWidget()
    try:
        host.resize(1024, 740)
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        view = shown(qapp, size=(1024, 740))
        layout.addWidget(view)
        host.show()

        scroll = view.findChild(QScrollArea, "bentoScroll")
        assert scroll is not None
        bar = scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
        qapp.processEvents()

        toast = Toast(host, view)
        toast.show_message("Moved block", "Undo")
        QTest.qWait(1200)
        qapp.processEvents()

        card = _toast_card_in_host(toast, host)
        for label in view.findChildren(QLabel):
            if not label.isVisible() or not label.text():
                continue
            ink = _visible_text_ink_in_host(label, host)
            assert not ink.intersects(card.toAlignedRect()), (
                f"Label {label.objectName()} '{label.text()}' at {ink.boundingRect().getRect()} "
                f"collides with card {card.getRect()}"
            )
    finally:
        host.close()
        host.deleteLater()
        qapp.processEvents()


def test_wrapped_ink_oracle_catches_unwrapped_metrics(qapp: QApplication) -> None:
    """Prove that ignoring TextWordWrap on a wrapped label produces an invalid ink oracle.

    A narrow 72px-wide QLabel with wordWrap=True produces unwrapped single-line bounds
    (width >> 72, 1 line height) vs. wrapping-aware bounds (width <= 72, multiline height).
    """
    host = QWidget()
    try:
        host.resize(200, 200)
        label = QLabel("Drag one onto the week.", host)
        label.setWordWrap(True)
        label.resize(72, 80)
        host.show()
        qapp.processEvents()

        raw_flags = int(label.alignment())
        unwrapped_rect = label.fontMetrics().boundingRect(label.rect(), raw_flags, label.text())

        wrapped_flags = raw_flags | int(Qt.TextFlag.TextWordWrap)
        wrapped_rect = label.fontMetrics().boundingRect(label.rect(), wrapped_flags, label.text())

        # Unwrapped fontMetrics overflows the 72px label width
        assert unwrapped_rect.width() > 72, (
            f"Unwrapped rect width {unwrapped_rect.width()} expected to overflow 72px"
        )
        # Wrapping-aware fontMetrics respects width and wraps across multiple lines
        assert wrapped_rect.width() <= 72, (
            f"Wrapping-aware rect width {wrapped_rect.width()} must not exceed label width 72"
        )
        assert wrapped_rect.height() > unwrapped_rect.height(), (
            f"Wrapped height {wrapped_rect.height()} must exceed single-line height {unwrapped_rect.height()}"
        )

        # _text_ink_in_host must use wrapping-aware metrics
        ink = _text_ink_in_host(label, host)
        assert ink.width() <= 72
        assert ink.height() > unwrapped_rect.height()
    finally:
        host.close()
        host.deleteLater()
        qapp.processEvents()


def test_undo_action_preserved_and_interactive(qapp: QApplication) -> None:
    """Preserve Undo action: clicking or keyboard Space triggers callback and closes notice."""
    host = QWidget()
    try:
        host.resize(1280, 800)
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        view = shown(qapp, size=(1280, 800))
        layout.addWidget(view)
        host.show()

        undone = []
        toast = Toast(host, view)
        toast.show_message("Moved block", "Undo", callback=lambda: undone.append(True))
        toast.reposition()
        qapp.processEvents()

        assert toast.isVisible()
        assert toast.button.isVisible()
        assert "Undo" in toast.button.text()

        # Keyboard activation via Space
        toast.button.setFocus()
        qapp.processEvents()
        assert toast.button.hasFocus(), "Undo button must receive keyboard focus"
        QTest.keyClick(toast.button, Qt.Key.Key_Space)
        qapp.processEvents()

        assert undone == [True], "Undo callback must be invoked on keyboard Space"
        assert not toast.isVisible(), "Toast notice must close/hide after Undo activation"

        # Mouse click activation on a fresh toast
        undone_mouse = []
        toast2 = Toast(host, view)
        toast2.show_message("Another move", "Undo", callback=lambda: undone_mouse.append(True))
        toast2.reposition()
        qapp.processEvents()

        assert toast2.isVisible()
        toast2.button.click()
        qapp.processEvents()

        assert undone_mouse == [True], "Undo callback must be invoked on click"
        assert not toast2.isVisible()
    finally:
        host.close()
        host.deleteLater()
        qapp.processEvents()
