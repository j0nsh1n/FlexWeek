"""The Undo notice stays through a design change and a view switch and still undoes, and goes when
the week changes, because its Undo is for that week."""

from __future__ import annotations

import importlib.util

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Desktop dependencies absent"
)

if importlib.util.find_spec("PySide6") is not None:
    from PySide6.QtWidgets import QAbstractButton, QApplication

    from desktop.native.layouts.registry import sanitize_layout
    from desktop.native.window import NativeWindow
    from desktop.tests.light_app import window  # noqa: F401
    from desktop.tests.test_week_side import seeded
    from desktop.tests.window_support import qapp, settled  # noqa: F401


def test_the_undo_toast_survives_a_design_change_and_still_undoes(
    qapp: QApplication, window: NativeWindow  # noqa: F811
) -> None:
    seeded(qapp, window)
    window.toast.hide()
    steps = len(window.session._undo)
    assert steps, "the seeding left a change to take back"
    window._set_notice("Moved History essay to Fri 18:00.", "Undo", window._undo_from_notice)
    for main in ("clay", "retro", "classic"):
        window._layout = sanitize_layout({"main": main, "day": "one"})
        window._apply_appearance()
        window._on_week()
        qapp.processEvents()
        assert window.toast.isVisible() and window.toast.button.isVisible(), main
    window.findChild(QAbstractButton, "viewMonth").click()
    settled(qapp, window)
    assert window.toast.button.isVisible()
    window.toast.button.click()
    settled(qapp, window)
    assert len(window.session._undo) == steps - 1, "the Undo used from Month took the step back"
    assert window.toast.text() != "Moved History essay to Fri 18:00.", "used, the old notice goes"


def test_the_toast_goes_when_the_week_changes_because_its_undo_is_for_that_week(
    qapp: QApplication, window: NativeWindow  # noqa: F811
) -> None:
    """Undo says "applies to the week where that change was saved" anywhere else, so a toast offering
    it would offer something that does nothing."""
    seeded(qapp, window)
    window._set_notice("Moved History essay to Fri 18:00.", "Undo", window._undo_from_notice)
    window._go_next()
    settled(qapp, window)
    assert not window.toast.isVisible() and not window.toast.button.isVisible()
