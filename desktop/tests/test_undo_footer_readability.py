"""Regression tests for W5: Undo toast footer readability in Bento layout.

Ensures settled Undo toast does not obscure the 'Not placed yet' instruction
(bentoWaitingHint) or other footer text in BentoView.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QRectF
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
    ink = label.fontMetrics().boundingRect(label.rect(), int(label.alignment()), label.text())
    ink.translate(label.mapTo(host, QPoint(0, 0)))
    return QRectF(ink)


def _toast_card_in_host(toast: Toast, host: QWidget) -> QRectF:
    """Return toast card bounding rectangle in host coordinates."""
    return QRectF(toast.card.mapTo(host, QPoint(0, 0)), toast.card.size())


def test_settled_undo_toast_does_not_obscure_bento_waiting_instruction(qapp: QApplication) -> None:
    """W5: Settled Undo toast at 1280x820 must not obscure bentoWaitingHint ink.

    Fails old geometry where bentoWaitingHint sat at the bottom of bentoWaiting
    (after box.addStretch(1)), intersecting the settled toast card at y in [753, 804].
    """
    host = QWidget()
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
    assert not card.intersects(ink), (
        f"Settled toast card {card.getRect()} collides with bentoWaitingHint ink {ink.getRect()}"
    )
    # Hint must sit clearly above the toast card
    assert ink.bottom() < card.top(), f"Expected ink.bottom {ink.bottom()} < card.top {card.top()}"

    host.close()


@pytest.mark.parametrize("size", [(1280, 800), (1280, 820), (1024, 740)])
@pytest.mark.parametrize("scale", [1.0, 1.2])
def test_undo_toast_readability_across_sizes_and_scales(
    qapp: QApplication, size: tuple[int, int], scale: float
) -> None:
    """Verify bentoWaitingHint paint bounds remain unobscured across normal and large scales."""
    host = QWidget()
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

    assert not card.intersects(ink), (
        f"size={size} scale={scale}: card {card.getRect()} collides with hint {ink.getRect()}"
    )
    host.close()


def test_cramped_1024x740_scroll_bottom_reach_unobscured(qapp: QApplication) -> None:
    """At 1024x740 cramped mode, scrolling to maximum bottom must not collide with toast."""
    host = QWidget()
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
        if label.isVisible() and label.text():
            ink = _text_ink_in_host(label, host)
            assert not card.intersects(ink), (
                f"Label {label.objectName()} '{label.text()}' at {ink.getRect()} "
                f"collides with card {card.getRect()}"
            )
    host.close()


def test_undo_action_preserved_and_interactive(qapp: QApplication) -> None:
    """Preserve Undo action: clicking Undo triggers callback and closes notice."""
    host = QWidget()
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

    toast.button.click()
    qapp.processEvents()

    assert undone == [True], "Undo callback must be invoked on click"
    host.close()
