"""All weeks, Except edited and From today on, through the client, for a Wednesday and a Sunday week.

The clock is Thursday 5 November 2026. Stored weeks are read back from the server.
"""

# ruff: noqa: F811
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.native.controller import NativeSession  # noqa: E402
from desktop.tests.e2e.account_sessions import server  # noqa: E402, F401
from desktop.tests.e2e.saved_weeks import read_week  # noqa: E402
from desktop.tests.e2e.test_a_week_from_any_day_saves_to_its_stored_weeks import (  # noqa: E402
    SUNDAY,
    WEDNESDAY,
    signed_in_from,
)
from desktop.tests.logic_support import settled  # noqa: E402
from desktop.tests.waiting import wait_until  # noqa: E402
from desktop.tests.week.test_standing_week import SCHOOL, SOCCER  # noqa: E402
from desktop.tests.window_support import qapp  # noqa: E402, F401

WEEKS = (
    "2026-10-26",
    "2026-11-02",
    "2026-11-09",
    "2026-11-16",
    "2026-11-23",
    "2026-11-30",
)


def finish(qapp: QApplication, session: NativeSession) -> None:
    wait_until(qapp, lambda: not session.busy and not session.dirty and session.pending_save is None)
    settled(qapp, session)


def go(qapp: QApplication, session: NativeSession, week: str) -> None:
    session.load_week(week)
    wait_until(qapp, lambda: session.week_start == week and not session.busy)
    settled(qapp, session)


def schools(week: dict) -> list[tuple[str, str, int, list[int]]]:
    rows = [
        (block["id"], block["start"], block["duration_min"], list(block["days"]))
        for block in week["blocks"]
        if str(block["id"]).split("@", 1)[0] == "school"
    ]
    return sorted(rows)


def saved(qapp: QApplication, session: NativeSession) -> dict[str, list]:
    return {week: schools(read_week(qapp, session, week)) for week in WEEKS}


FULL = ("school", "08:30", 360, [0, 1, 2, 3, 4])
OLD = ("school", "08:30", 405, [0, 1, 2, 3, 4])


@pytest.mark.parametrize("mode", ["keep", "replace", "from_today"])
@pytest.mark.parametrize("first,opening", [(WEDNESDAY, "2026-11-04"), (SUNDAY, "2026-11-01")])
def test_each_choice_through_the_client(
    qapp, server, mode: str, first: int, opening: str
) -> None:
    session = signed_in_from(qapp, server.origin, f"c{mode[0]}{first}", first)
    assert session.week_start == opening
    session.set_setup_blocks([dict(SCHOOL), dict(SOCCER)])
    session.save()
    finish(qapp, session)
    later = "2026-11-18" if first == WEDNESDAY else "2026-11-15"
    go(qapp, session, later)
    session.delete_block("school", scope="occurrence", day=2)
    session.save()
    finish(qapp, session)
    go(qapp, session, opening)
    session.set_setup_blocks([{**SCHOOL, "duration_min": 360}, dict(SOCCER)], edited=mode)
    session.save()
    finish(qapp, session)
    found = saved(qapp, session)
    if first == WEDNESDAY and mode == "replace":
        assert found["2026-11-02"] == [("school", "08:30", 360, [2, 3, 4])]
        assert found["2026-11-09"] == [FULL]
        assert found["2026-11-16"] == [FULL]
    elif first == WEDNESDAY and mode == "keep":
        assert found["2026-11-02"] == [("school", "08:30", 360, [2, 3, 4])]
        assert found["2026-11-09"] == [FULL]
        assert found["2026-11-16"] == [("school", "08:30", 360, [0, 1, 2, 3])]
    elif first == WEDNESDAY and mode == "from_today":
        assert found["2026-11-02"] == [("school", "08:30", 405, [2, 3, 4])]
        assert found["2026-11-09"] == [
            ("school", "08:30", 405, [0, 1]),
            ("school@20261111", "08:30", 360, [2, 3, 4]),
        ]
        assert found["2026-11-16"] == [FULL]
    elif first == SUNDAY and mode == "replace":
        assert found["2026-10-26"] == []
        assert found["2026-11-02"] == [FULL]
        assert found["2026-11-16"] == [FULL]
    elif first == SUNDAY and mode == "keep":
        assert found["2026-10-26"] == []
        assert found["2026-11-02"] == [FULL]
        assert found["2026-11-16"] == [("school", "08:30", 360, [0, 2, 3, 4])]
    else:
        assert found["2026-10-26"] == []
        assert found["2026-11-02"] == [OLD]
        assert found["2026-11-09"] == [FULL]


def test_from_today_on_a_later_open_week_reaches_the_weeks_between(qapp, server) -> None:
    session = signed_in_from(qapp, server.origin, "lateropen", 0)
    assert session.week_start == "2026-11-02"
    session.set_setup_blocks([dict(SCHOOL), dict(SOCCER)])
    session.save()
    finish(qapp, session)
    go(qapp, session, "2026-11-30")
    session.delete_block("school", scope="occurrence", day=2)
    session.save()
    finish(qapp, session)
    go(qapp, session, "2026-11-23")
    session.set_setup_blocks([{**SCHOOL, "duration_min": 360}, dict(SOCCER)], edited="from_today")
    session.save()
    finish(qapp, session)
    found = saved(qapp, session)
    assert found["2026-11-02"] == [OLD]
    assert found["2026-11-09"] == [FULL]
    assert found["2026-11-16"] == [FULL]
    assert found["2026-11-23"] == [FULL]
    assert found["2026-11-30"] == [FULL]
    december = schools(read_week(qapp, session, "2026-12-07"))
    assert december == [FULL]
