# ruff: noqa: F811
"""The week tools Material's More menu gained: Copy day, Copy last week's fixed times, Reload this week
and Open Spotify link. Each does what the plain look's tool does, is greyed while a save runs, and
Open Spotify link is there only with a link set.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from desktop.native.window import NativeWindow  # noqa: E402
from desktop.tests.sheets.support_material_sheet_fixtures import (  # noqa: E402,F401
    open_light,
    qapp,
    sheets,
    shell,
)

TOOLS = ("copyDay", "copyLastWeek", "reloadWeek", "openSpotify")
LINK = "https://open.spotify.com/playlist/37i9dQZF1DX8Uebhn9wzrS"


def _rows(sheets) -> dict:
    sheets.openMore()
    return {row["id"]: row for row in sheets.moreEntries if row["id"]}


def test_tools_sit_under_planning_with_the_plain_looks_words(shell: NativeWindow, sheets) -> None:
    rows = _rows(sheets)
    assert rows["copyDay"]["label"] == "Copy day"
    assert rows["copyLastWeek"]["label"] == "Copy last week's fixed times"
    assert rows["reloadWeek"]["label"] == "Reload this week"
    # Today is Thursday, the day Copy day would copy in the week view.
    assert rows["copyDay"]["detail"] == "Thursday"
    ids = [row["id"] for row in sheets.moreEntries]
    assert ids.index("copyDay") < ids.index("helpButton")
    assert [row["heading"] for row in sheets.moreEntries if row["heading"]] == [
        "Planning",
        "Help and info",
        "Account",
    ]


def test_spotify_row_needs_a_link(shell: NativeWindow, sheets, monkeypatch: pytest.MonkeyPatch) -> None:
    assert "openSpotify" not in _rows(sheets)
    sheets.closeMore()
    shell.session.preferences["default_spotify_url"] = LINK
    opened: list[str] = []
    monkeypatch.setattr("desktop.native.window.open_in_app", lambda url: opened.append(url))
    rows = _rows(sheets)
    assert rows["openSpotify"]["label"] == "Open Spotify link"
    assert rows["openSpotify"]["enabled"] is True
    sheets.moreAction("openSpotify")
    assert opened == [LINK]
    assert sheets.moreOpen is False


def test_copy_day_puts_the_day_on_the_clipboard(shell: NativeWindow, sheets) -> None:
    _rows(sheets)
    sheets.moreAction("copyDay")
    clip = shell.session.clipboard
    assert clip is not None
    assert clip["kind"] == "day"
    # School and the essay, both on Thursday.
    assert clip["label"] == "Thursday · 2 items"
    assert sheets.moreOpen is False


def test_copy_last_week_offers_a_preview_or_says_there_is_nothing(
    shell: NativeWindow, sheets, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple] = []
    monkeypatch.setattr(shell, "_show_preview", lambda *a, **kw: seen.append((a, kw)))
    monkeypatch.setattr(
        shell.session,
        "copy_last_week_fixed_rows",
        lambda done: done([{"id": "x", "title": "Choir", "checked": True}]),
    )
    _rows(sheets)
    sheets.moreAction("copyLastWeek")
    assert len(seen) == 1
    args, kw = seen[0]
    assert args[0] == "Copy last week's fixed times"
    assert kw["label"] == "last week's fixed times"
    seen.clear()
    monkeypatch.setattr(shell.session, "copy_last_week_fixed_rows", lambda done: done(None))
    _rows(sheets)
    sheets.moreAction("copyLastWeek")
    assert seen == []


def test_reload_reads_the_week_again(shell: NativeWindow, sheets, monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []
    monkeypatch.setattr(shell.session, "reload", lambda: called.append("reload"))
    _rows(sheets)
    sheets.moreAction("reloadWeek")
    assert called == ["reload"]


def test_reload_really_reloads_and_says_so(qapp, shell: NativeWindow, sheets) -> None:
    from desktop.tests.waiting import wait_until

    shell.session.dirty = False
    _rows(sheets)
    sheets.moreAction("reloadWeek")
    wait_until(qapp, lambda: not shell.session.busy, what="the reload to finish")
    assert any(item["id"] == "school" for item in shell.session.blocks)


def test_tools_grey_while_a_save_is_running(
    shell: NativeWindow, sheets, monkeypatch: pytest.MonkeyPatch
) -> None:
    shell.session.preferences["default_spotify_url"] = LINK
    pressed: list[str] = []
    monkeypatch.setattr(shell, "_copy_day", lambda: pressed.append("copyDay"))
    monkeypatch.setattr(shell, "_copy_last_week_fixed", lambda: pressed.append("copyLastWeek"))
    monkeypatch.setattr(shell, "_open_spotify", lambda: pressed.append("openSpotify"))
    monkeypatch.setattr(shell.session, "reload", lambda: pressed.append("reloadWeek"))
    shell.session.busy = True
    try:
        rows = _rows(sheets)
        assert all(rows[name]["enabled"] is False for name in TOOLS)
        for name in TOOLS:
            sheets.moreAction(name)
        assert pressed == []
    finally:
        shell.session.busy = False
    rows = _rows(sheets)
    assert all(rows[name]["enabled"] is True for name in TOOLS)
