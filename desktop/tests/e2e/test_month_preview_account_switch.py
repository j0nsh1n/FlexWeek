# ruff: noqa: F811
"""The Settings month preview never shows one account's homework to the next account signed in on the
same computer. Signing out and creating a second account needs the real local server, so this one
stays end to end."""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from desktop.tests.material_support import pump
from desktop.tests.month.support_material_month import bridge, panel, totals
from desktop.tests.test_material_account_setup import (
    create,
    launches,  # noqa: F401
    qapp,  # noqa: F401
    settle,
    sign_out,
    skip_setup,
    through_recovery,
)
from desktop.tests.waiting import wait_until


def test_real_account_replacement_does_not_keep_personal_counts(qapp: Any, launches: Any) -> None:
    win = launches.launch()
    s = win.session
    create(qapp, win, "cold_owner_a")
    through_recovery(qapp, win)
    skip_setup(qapp, win)
    pump(qapp)

    preview = panel(win)._preview._passive_month

    # Homework saved on the current week (2-8 November) and on the week two weeks on.
    s.add_block(
        {
            "id": "owner-a-personal",
            "title": "Owner A private homework",
            "kind": "locked",
            "category": "homework",
            "start": "17:00",
            "duration_min": 75,
            "days": [0, 1, 2, 3, 4, 5, 6],
        }
    )
    s.save()
    settle(qapp, win)

    home_week = s.week_start
    future = (date.fromisoformat(home_week) + timedelta(days=14)).isoformat()
    s.load_week(future)
    settle(qapp, win)
    s.add_block(
        {
            "id": "owner-a-future",
            "title": "Owner A private future homework",
            "kind": "locked",
            "category": "homework",
            "start": "17:00",
            "duration_min": 75,
            "days": [0, 1, 2, 3, 4, 5, 6],
        }
    )
    s.save()
    settle(qapp, win)
    s.load_week(home_week)
    settle(qapp, win)
    s._month_cache.clear()

    # Settings > Advanced > Month preview.
    bridge(win).showPage("settings")
    settings = panel(win)
    settings.openAdvanced()
    settings.setPreviewView("month")
    wait_until(qapp, lambda: preview._preview_snapshot is not None, timeout=5.0)

    old_account = s.account["id"]
    old_total = totals(preview)
    assert any(r["iso"] == future and r["plannedMin"] == 75 for r in preview.cellRows)
    assert old_total[0] > 7 * 75  # the full month has planned minutes from both weeks

    sign_out(qapp, win)
    pump(qapp)

    # As soon as the first account signs out the preview is empty.
    assert preview.dates.rowCount() == 0
    assert totals(preview) == (0, 0)
    assert preview._preview_snapshot is None

    # An empty second account.
    create(qapp, win, "cold_owner_b")
    through_recovery(qapp, win)
    skip_setup(qapp, win)
    settle(qapp, win)

    bridge(win).showPage("settings")
    settings = panel(win)
    settings.openAdvanced()
    settings.setPreviewView("month")
    wait_until(qapp, lambda: not preview.loading and preview.dates.rowCount() > 0)

    private = [r["iso"] for r in preview.cellRows if "Owner A private" in json.dumps(r)]
    assert s.account["id"] != old_account
    assert not s.blocks
    assert not private and totals(preview) == (0, 0), (
        "New account B displays previous account A full-month homework/counts"
    )
