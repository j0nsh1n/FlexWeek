"""The Settings month preview and the answers to its requests: an old answer, or one for another
month or account, never lands on the screen, and the preview never keeps another account's homework.

These run on a stand-in session whose client holds its requests, so the test decides in which order
the answers arrive."""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from desktop.native.client import ApiError
from desktop.native.material.bridge_settings import PassiveMonthBridge
from desktop.tests.month.support_material_month import Held, Live, dispose_lives, rig, snap, totals


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    yield QApplication.instance() or QApplication(["flexweek-month-preview-stale"])


@pytest.fixture(autouse=True)
def dispose_live(no_window_is_left_for_the_garbage_collector: Any) -> Iterator[None]:
    yield
    dispose_lives()


def test_target_month_change_drops_dedicated_snapshot(qapp: Any) -> None:
    session, held, live, preview = rig(qapp)
    held.calls[0][3](snap())
    assert totals(preview) == (75, 75)
    session.selected_month = "2026-12"
    session.month_data = snap("2026-12", "December homework")
    live.changed.emit()
    months = {r["iso"][:7] for r in preview.cellRows if r["inMonth"]}
    assert months == {"2026-12"}, "December target renders November after dedicated November GET"


def test_logout_clears_dedicated_snapshot_and_rows(qapp: Any) -> None:
    session, held, live, preview = rig(qapp)
    held.calls[0][3](snap())
    assert totals(preview) == (75, 75)
    session.account = None
    session._month_cache.clear()
    live.changed.emit()
    assert preview.dates.rowCount() == 0 and preview._preview_snapshot is None


def test_same_month_account_change_uses_new_account_cache(qapp: Any) -> None:
    session, held, live, preview = rig(qapp)
    held.calls[0][3](snap())
    session.account = {"id": "B"}
    session._month_cache = {("B", "2026-11"): {"month": "2026-11", "days": []}}
    live.changed.emit()
    assert totals(preview) == (0, 0), "Account B sees account A homework despite B-keyed empty cache"


def test_old_error_cannot_poison_new_success(qapp: Any) -> None:
    session, held, live, preview = rig(qapp)
    old = held.calls[0]
    session.selected_month = "2026-12"
    live.changed.emit()
    new = held.calls[1]
    new[3](snap("2026-12"))
    old[4](ApiError(503, "old November failure"))
    assert not preview._load_error, "Old November error overwrites successful December state"


def test_older_success_cannot_win_nov_dec_nov(qapp: Any) -> None:
    session, held, live, preview = rig(qapp)
    old_november = held.calls[0]
    session.selected_month = "2026-12"
    live.changed.emit()
    session.selected_month = "2026-11"
    live.changed.emit()
    newest_november = held.calls[2]
    newest_november[3]({"month": "2026-11", "days": []})
    assert totals(preview) == (0, 0)
    old_november[3](snap())
    assert totals(preview) == (0, 0), (
        "Older November request overwrites newer November success after Nov-Dec-Nov navigation"
    )


def test_cache_only_account_switch_positive_control(qapp: Any) -> None:
    held = Held()
    session = SimpleNamespace(
        account={"id": "A"},
        selected_month=None,
        month_data=None,
        preferences={},
        week_start=None,
        unsaved_weeks=lambda: {},
        today_iso=lambda: "2026-11-03",
        _month_cache={("A", "2026-11"): snap()},
        client=held,
    )
    live = Live(session)
    preview = PassiveMonthBridge(live, live)
    assert totals(preview) == (75, 75) and not held.calls
    session.account = {"id": "B"}
    session._month_cache = {("B", "2026-11"): {"month": "2026-11", "days": []}}
    live.changed.emit()
    assert totals(preview) == (0, 0) and not held.calls


def test_a_late_error_after_a_month_switch_clears_loading_for_the_new_month_only(qapp: Any) -> None:
    session, held, live, preview = rig(qapp)
    nov_call = held.calls[0]
    assert preview.loading

    # Switch month to December
    session.selected_month = "2026-12"
    live.changed.emit()
    assert len(held.calls) == 2
    dec_call = held.calls[1]
    assert preview.loading

    # Late error arrives for November
    nov_call[4](ApiError(500, "Nov server error"))

    # Must NOT clear loading because December is still loading
    assert preview.loading, "Late error for old month cleared loading for new month"
    assert preview.loadError == ""

    # Error arrives for December (the new month)
    dec_call[4](ApiError(503, "Dec server error"))

    # Now loading is cleared and error is set
    assert not preview.loading
    assert preview.loadError == "Dec server error"


def test_every_early_return_of_the_current_request_clears_loading(qapp: Any) -> None:
    # 1. ok: current_session is None
    session, held, live, preview = rig(qapp)
    call = held.calls[0]
    assert preview.loading
    live.session = None
    emitted: list[bool] = []
    preview.changed.connect(lambda: emitted.append(True))
    call[3](snap())
    assert not preview.loading
    assert len(emitted) > 0, "Early return 1 did not emit changed"

    # 2. ok: current_account is None or mismatched
    session, held, live, preview = rig(qapp)
    call = held.calls[0]
    assert preview.loading
    session.account = {"id": "OTHER"}
    emitted.clear()
    preview.changed.connect(lambda: emitted.append(True))
    call[3](snap())
    assert not preview.loading
    assert len(emitted) > 0, "Early return 2 did not emit changed"

    # 3. ok: invalid payload or mismatched month
    session, held, live, preview = rig(qapp)
    call = held.calls[0]
    assert preview.loading
    emitted.clear()
    preview.changed.connect(lambda: emitted.append(True))
    call[3]({"month": "2026-12", "days": []})
    assert not preview.loading
    assert len(emitted) > 0, "Early return 3 did not emit changed"

    # 4. err: current_session is None
    session, held, live, preview = rig(qapp)
    call = held.calls[0]
    assert preview.loading
    live.session = None
    emitted.clear()
    preview.changed.connect(lambda: emitted.append(True))
    call[4](ApiError(500, "error"))
    assert not preview.loading
    assert len(emitted) > 0, "Early return 4 did not emit changed"

    # 5. err: current_account is None or mismatched
    session, held, live, preview = rig(qapp)
    call = held.calls[0]
    assert preview.loading
    session.account = None
    emitted.clear()
    preview.changed.connect(lambda: emitted.append(True))
    call[4](ApiError(500, "error"))
    assert not preview.loading
    assert len(emitted) > 0, "Early return 5 did not emit changed"

    # 6. err: self._target_month() != target_month
    session, held, live, preview = rig(qapp)
    call = held.calls[0]
    assert preview.loading
    session.selected_month = "2026-12"
    emitted.clear()
    preview.changed.connect(lambda: emitted.append(True))
    call[4](ApiError(500, "error"))
    assert not preview.loading
    assert len(emitted) > 0, "Early return 6 did not emit changed"
