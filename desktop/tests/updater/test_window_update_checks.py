# ruff: noqa: F811
"""When the window asks for an update, what it says when the check fails, and the version a student
skipped."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.day.support_layouts_window import (  # noqa: E402
    FakeUpdater,
    qapp,  # noqa: F401
    wait_until,
    window,  # noqa: F401
)


def test_an_update_check_that_fails_says_so_only_when_asked(qapp: QApplication, window: NativeWindow) -> None:
    """GitHub refused the check (403, its hourly limit for a shared address) and the app said nothing, so
    "Checking for updates…" stayed on screen as if the check were still going."""
    from desktop.native.updater import CHECK_FAILED

    # The window's own check on opening is a real request; its answer, landing after _update_asked is
    # set below, would put "is the latest version" over the toast this test reads.
    wait_until(qapp, lambda: not window._updater.busy, timeout=30.0)
    window._update_asked = False
    window._updater.unreachable.emit(CHECK_FAILED)
    qapp.processEvents()
    assert window.toast.isVisible() is False, "a daily check that fails stays quiet"

    window._update_asked = True
    window._updater.unreachable.emit(CHECK_FAILED)
    qapp.processEvents()
    assert window.toast.button.isVisible() is True
    assert window.toast.text() == CHECK_FAILED
    assert window.toast.button.text() == "Open release page"


def test_the_app_checks_for_updates_once_a_day_not_every_week_refresh(
    qapp: QApplication, window: NativeWindow
) -> None:
    """_on_week runs on every save, solve and week change. Checking there without a cadence would ask
    GitHub dozens of times a session."""
    fake = FakeUpdater()
    window._updater = fake
    window._updates = {"check": True, "last_ms": 0, "skip": ""}
    window._on_week()
    qapp.processEvents()
    assert fake.checks == 1
    window._on_week()
    window._on_week()
    qapp.processEvents()
    assert fake.checks == 1, "a week refresh asked GitHub again"


def test_turning_update_checks_off_is_obeyed(qapp: QApplication, window: NativeWindow) -> None:
    fake = FakeUpdater()
    window._updater = fake
    window._updates = {"check": False, "last_ms": 0, "skip": ""}
    window._on_week()
    qapp.processEvents()
    assert fake.checks == 0


def test_asking_for_a_check_ignores_the_cadence(qapp: QApplication, window: NativeWindow) -> None:
    """Check for updates has to check, whatever the daily timer says."""
    fake = FakeUpdater()
    window._updater = fake
    window._updates = {"check": True, "last_ms": window.session.now_ms(), "skip": ""}
    window._check_updates(asked=True)
    assert fake.checks == 1


def test_a_skipped_version_stays_quiet_until_asked(qapp: QApplication, window: NativeWindow) -> None:
    window._updates = {"check": True, "last_ms": 0, "skip": "9.9.9"}
    window._update_asked = False
    window._on_update_found({"version": "9.9.9", "asset": "x", "url": "u", "checksum_url": "c", "notes": ""})
    assert window._update_dialog is None
