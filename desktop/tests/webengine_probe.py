"""Isolated Qt integration probe, launched by test_webengine.py."""

from __future__ import annotations

import contextlib
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from PySide6.QtCore import QEventLoop, QTimer, QUrl
from PySide6.QtGui import QCloseEvent
from PySide6.QtTest import QTest
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEnginePermission
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from backend.assignments import migrated_assignment_id
from desktop.main import (
    OFFLINE_HEADING,
    PAGE_STOPPED_HEADING,
    PAINTED_MIN_COLORS,
    MainWindow,
    instance_name,
    painted_colors,
    show_running_instance,
)
from desktop.server import LocalServer


def run(case: str, root: Path) -> None:
    app = QApplication([])
    app.setApplicationName("FlexWeek-test")
    server = LocalServer(root / "account.db")
    origin = server.start()
    window = MainWindow(origin, tray_enabled=case == "tray")
    window.show()
    page = window._page
    opened: list[str] = []

    def record_external(url: QUrl) -> bool:
        opened.append(url.toString())
        return True

    def evaluate(code: str):
        loop = QEventLoop()
        values = []

        def receive(value):
            values.append(value)
            loop.quit()

        page.runJavaScript(code, receive)
        QTimer.singleShot(3000, loop.quit)
        loop.exec()
        assert values, "JavaScript callback timed out"
        return values[0]

    def wait_for(code: str, timeout: float = 10.0) -> None:
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            if evaluate(f"Boolean({code})"):
                return
            QTest.qWait(50)
        raise AssertionError(f"Condition not reached: {code}")

    def submit_identity(name: str, action: str, acknowledge_codes: bool = True) -> list[str]:
        evaluate(f"""if (document.getElementById('{action}-screen').hidden)
                document.getElementById('show-{action}').click();
            document.getElementById('{action}-username').value={json.dumps(name)};
            document.getElementById('{action}-password').value='temporary-test-password';
            document.querySelector('#{action}-form button[type=submit]').click();""")
        wait_for(f"document.getElementById('account-name').textContent === {json.dumps(name)}")
        wait_for("!document.getElementById('planner').hidden")
        codes: list[str] = []
        if action == "register":
            wait_for("document.getElementById('recovery-codes-dialog').open")
            wait_for("document.querySelectorAll('#recovery-codes-list code').length === 8")
            codes = cast(list[str], json.loads(evaluate(
                "JSON.stringify(Array.from(document.querySelectorAll('#recovery-codes-list code'), "
                "node => node.textContent))"
            )))
            if acknowledge_codes:
                evaluate("""document.getElementById('recovery-codes-ack').checked=true;
                    document.getElementById('recovery-codes-ack').dispatchEvent(new Event('change'));
                    document.getElementById('recovery-codes-done').click();""")
                wait_for("!document.getElementById('recovery-codes-dialog').open")
        return codes

    def wait_through_reload(code: str, timeout: float = 20.0) -> None:
        """wait_for across a page that is gone or reloading, when scripts cannot answer."""
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            with contextlib.suppress(AssertionError):
                if evaluate(f"Boolean({code})"):
                    return
            QTest.qWait(100)
        raise AssertionError(f"Condition not reached: {code}")

    def api_json(path: str) -> dict:
        """GET an API path with the page's session; a failed request comes back as {"status": code}."""
        evaluate(f"window.__apiReply = undefined; api({json.dumps(path)}).then("
                 "data => { window.__apiReply = JSON.stringify(data); }, "
                 "error => { window.__apiReply = JSON.stringify({status: error.status}); })")
        wait_for("typeof window.__apiReply === 'string'")
        return cast(dict, json.loads(evaluate("window.__apiReply")))

    def assert_painted(label: str) -> None:
        QTest.qWait(300)
        colors = painted_colors(window.grab().toImage())
        assert colors >= PAINTED_MIN_COLORS, f"{label}: the window is blank ({colors} colors)"

    def finish_setup_with_homework() -> None:
        """Setup as a rookie leaves it: school defaults, no sport, one homework, then Solve."""
        wait_for("document.getElementById('setup-dialog').open")
        evaluate("document.getElementById('setup-next').click()")
        evaluate("document.getElementById('setup-skip').click()")
        evaluate("""document.getElementById('setup-homework-title').value='Math worksheet';
            document.getElementById('setup-next').click();""")
        assert evaluate("document.getElementById('setup-next').textContent") == "Add to my week and plan"
        evaluate("document.getElementById('setup-next').click()")

    solved_week = (
        "!document.getElementById('setup-dialog').open && !document.getElementById('debug').hidden && "
        "document.querySelectorAll('.flex-block').length === 1"
    )

    def page_theme() -> object:
        return evaluate("document.documentElement.dataset.theme")

    def theme_menu() -> object:
        return evaluate("document.getElementById('theme').value")

    def add_item(category: str, fields: str, days: list[int] | None = None) -> None:
        """Pick a type chip, open Add without dragging, fill the dialog and save it."""
        only_days = "" if days is None else (
            f"document.getElementById('f-when-day').value='{days[0]}';"
            f"[0,1,2,3,4,5,6].forEach(d => document.getElementById('f-day-'+d).checked = "
            f"{json.dumps(days)}.includes(d));"
        )
        evaluate(f"""document.querySelector('#type-chips [data-category={category}]').click();
            document.getElementById('add-block').click();
            {fields} {only_days}
            document.querySelector('#block-form button[type=submit]').click();""")

    try:
        window.load_app()
        wait_for(
            "document.getElementById('status') && "
            "document.getElementById('status').textContent.includes('Create an account')"
        )
        assert evaluate("!document.getElementById('register-screen').hidden"), "First screen is not sign-up"
        device_theme = evaluate("matchMedia('(prefers-color-scheme: dark)').matches ? 'nocturne' : 'slate'")
        assert page_theme() == device_theme, "Signed-out screen ignores device"
        assert evaluate("document.getElementById('login-screen').hidden"), "Log in shown on first launch"
        if case == "accounts":
            # The vendored Figtree face must actually load, not fall back to a system font.
            wait_for("Array.from(document.fonts).some(face => face.family.replace(/\"/g, '') === 'Figtree' "
                     "&& face.status === 'loaded')")
            submit_identity("first_student", "register")
            add_item("class", "document.getElementById('f-title').value='School';", days=[0])
            wait_for("document.getElementById('status').textContent.startsWith('Saved')")
            assert evaluate("document.querySelectorAll('.block').length") == 1
            evaluate("document.getElementById('solve').click()")
            wait_for("!document.getElementById('debug').hidden")
            assert theme_menu() == "system", "New account is not on System"
            evaluate(
                "document.getElementById('theme').value='nocturne'; "
                "document.getElementById('theme').dispatchEvent(new Event('change'))"
            )
            wait_for("!document.getElementById('theme').disabled")
            evaluate("window.__beforeReload=true")
            window.reload()
            wait_for(
                "typeof window.__beforeReload === 'undefined' && document.getElementById('planner') && "
                "!document.getElementById('planner').hidden"
            )
            assert page_theme() == "nocturne", "Chosen Dark did not persist"
            assert evaluate("document.querySelectorAll('.block').length") == 1
            evaluate("document.getElementById('logout').click()")
            wait_for("document.getElementById('planner').hidden")
            assert evaluate("document.querySelectorAll('.block').length") == 0
            submit_identity("second_student", "register")
            assert evaluate("document.querySelectorAll('.block').length") == 0
            assert theme_menu() == "system"
            assert page_theme() == device_theme, "New account ignores device"
            evaluate("document.getElementById('logout').click()")
            wait_for("document.getElementById('planner').hidden")
            assert evaluate("!document.getElementById('login-screen').hidden"), "Log out did not open Log in"
            submit_identity("first_student", "login")
            assert evaluate("document.querySelectorAll('.block').length") == 1
            for width in (1280, 390):
                window.resize(width, 800)
                QTest.qWait(100)
                assert window.width() == width, (window.width(), width)
                window.grab().save(str(root / f"planner-{width}.png"))
                assert evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (
                    f"Overflow at {width}px"
                )
            print(
                "PASS: register, editor save, solve, refresh, theme, logout, second-account isolation, widths"
            )
        elif case == "system_dark":
            # Launched with Chromium told the device prefers dark (see test_webengine.py).
            assert device_theme == "nocturne", "The dark device preference did not reach the page"
            submit_identity("night_student", "register")
            assert theme_menu() == "system"
            assert page_theme() == "nocturne"
            evaluate("document.getElementById('setup-close').click()")
            evaluate(
                "document.getElementById('theme').value='slate'; "
                "document.getElementById('theme').dispatchEvent(new Event('change'))"
            )
            wait_for("!document.getElementById('theme').disabled")
            evaluate("window.__beforeReload=true")
            window.reload()
            wait_for(
                "typeof window.__beforeReload === 'undefined' && document.getElementById('planner') && "
                "!document.getElementById('planner').hidden"
            )
            assert page_theme() == "slate", "Chosen Light lost to the dark device"
            print("PASS: a dark device starts dark, and a chosen Light theme persists over it")
        elif case == "rookie":
            submit_identity("rookie_student", "register")
            wait_for("document.getElementById('setup-dialog').open")
            assert evaluate("document.getElementById('setup-progress').textContent") == "Step 1 of 4"
            evaluate("document.getElementById('setup-next').click()")
            evaluate("""document.getElementById('setup-sports-title').value='Soccer';
                document.getElementById('setup-sports-day-1').checked=true;
                document.getElementById('setup-next').click();""")
            evaluate("""document.getElementById('setup-homework-title').value='Math worksheet';
                document.getElementById('setup-homework-due-date').value=dateForDay(selectedWeek, 6);
                document.getElementById('setup-next').click();""")
            assert "Math worksheet" in evaluate("document.getElementById('setup-summary').textContent")
            evaluate("document.getElementById('setup-next').click()")
            wait_for("!document.getElementById('debug').hidden")
            assert not evaluate("document.getElementById('setup-dialog').open")
            assert evaluate("document.getElementById('empty-week').hidden")
            assert evaluate("document.querySelectorAll('.block:not(.flex-block)').length") == 6
            assert evaluate("document.querySelectorAll('.flex-block').length") == 1, "Homework was not placed"
            stats = evaluate("document.getElementById('debug-stats').textContent")
            assert stats == "1 task fits.", stats
            assert not evaluate("Array.from(document.querySelectorAll('.slack-badge'))"
                                ".some(b => /slack/i.test(b.textContent))"), "Raw slack jargon on the grid"
            assert not evaluate("document.getElementById('focus-section').hidden")
            window.grab().save(str(root / "rookie-solved.png"))
            assert_painted("After the setup Solve")
            evaluate("document.getElementById('logout').click()")
            wait_for("!document.getElementById('login-screen').hidden")
            submit_identity("rookie_student", "login")
            assert not evaluate("document.getElementById('setup-dialog').open"), "Setup reopened on login"
            assert evaluate("document.querySelectorAll('.block').length") == 6
            print("PASS: register, setup, Solve with plain results, log out and log back in")
        elif case == "recovery":
            submit_identity("crash_student", "register")
            finish_setup_with_homework()
            wait_for(solved_week)
            assert_painted("After the setup Solve")
            assert evaluate("getComputedStyle(document.querySelector('.side')).backdropFilter") != "none"
            # The page process dies, as it did for v0.9.0 testers: the window must come back by itself.
            os.kill(page.renderProcessPid(), signal.SIGKILL)
            wait_through_reload(
                f"location.search === '' && document.documentElement.dataset.frost === 'off' && {solved_week}"
            )
            assert window._stack.currentIndex() == 0
            status = evaluate("document.getElementById('status').textContent")
            assert status.startswith("FlexWeek reopened after a display problem. Saved week"), status
            assert evaluate("getComputedStyle(document.querySelector('.side')).backdropFilter") == "none"
            assert evaluate("document.getElementById('debug-stats').textContent") == "1 task fits."
            assert_painted("After recovering the page")
            # Stopping again right away gets a native message instead of a reload loop.
            os.kill(page.renderProcessPid(), signal.SIGKILL)
            until = time.monotonic() + 10
            while window._stack.currentIndex() != 1 and time.monotonic() < until:
                QTest.qWait(50)
            assert window._stack.currentIndex() == 1, "A second stop did not show the native panel"
            assert window._retry.heading.text() == PAGE_STOPPED_HEADING
            window._retry.button.click()
            wait_through_reload(solved_week)
            assert window._stack.currentIndex() == 0
            # A later failed load shows the offline panel, whose Reload is an ordinary load again.
            window._on_load_finished(False)
            assert window._retry.heading.text() == OFFLINE_HEADING
            with patch.object(window, "load_app") as ordinary_load:
                window._retry.button.click()
            ordinary_load.assert_called_once_with()
            print("PASS: setup Solve paints, a stopped page reopens solved, a second stop shows a panel")
        elif case == "calendar":
            submit_identity("calendar_student", "register")
            evaluate("""window.__point = (type, minute, onBlock=false, pointerId=1) => {
                const lane = document.querySelector('.day-lane');
                const rect = lane.getBoundingClientRect();
                const target = onBlock ? lane.querySelector('.block') : lane;
                target.dispatchEvent(new PointerEvent(type, {bubbles:true, cancelable:true,
                    pointerId, button:0, clientX:rect.left+20,
                    clientY:rect.top + (minute-360)/1020*rect.height}));
            };""")
            def gesture(start: int, end: int, *, block: bool = False, cancel: bool = False) -> None:
                event = "pointercancel" if cancel else "pointerup"
                evaluate(f"__point('pointerdown', {start}, {json.dumps(block)}); "
                         f"__point('pointermove', {end}); __point('{event}', {end})")

            def edit_card() -> None:
                evaluate("document.querySelector('.block').dispatchEvent("
                         "new MouseEvent('dblclick', {bubbles:true}))")

            evaluate("document.querySelector('#type-chips [data-category=class]').click()")
            # 0.11: picking a type chip is the whole gesture, so Add opens with it chosen.
            wait_for("document.getElementById('block-dialog').open")
            assert evaluate("document.getElementById('f-category').value") == "class", \
                "Chip did not choose the type"
            evaluate("document.getElementById('form-cancel').click()")
            assert not evaluate("document.getElementById('block-dialog').open"), "Cancel left the editor open"
            gesture(600, 660, cancel=True)
            QTest.qWait(100)
            assert evaluate("document.querySelectorAll('.block').length") == 0, "Cancelled create"
            assert not evaluate("document.getElementById('block-dialog').open"), "Cancel opened editor"
            assert evaluate("document.querySelector('.drag-ghost').hidden")
            evaluate("__point('pointerdown', 600); __point('pointermove', 643, false, 2); "
                     "__point('pointerup', 643, false, 2)")
            assert evaluate("document.querySelectorAll('.block').length") == 0, "Second pointer committed"
            evaluate("__point('pointercancel', 600)")
            gesture(600, 643)
            wait_for("document.getElementById('block-dialog').open")
            assert evaluate("document.querySelectorAll('.block').length") == 0, "Added before Save"
            assert evaluate("document.getElementById('f-start').value") == "10:00"
            assert evaluate("document.getElementById('f-end').value") == "10:45"
            evaluate("document.querySelector('#block-form button[type=submit]').click()")
            wait_for("document.getElementById('status').textContent.startsWith('Saved')")
            assert not evaluate("document.getElementById('block-dialog').open")
            assert evaluate("document.querySelectorAll('.block').length") == 1
            assert evaluate("document.querySelector('.block .title').textContent") == "School"
            edit_card()
            assert evaluate("document.getElementById('f-start').value") == "10:00"
            assert evaluate("document.getElementById('f-end').value") == "10:45"
            evaluate("document.getElementById('form-cancel').click()")
            gesture(622, 652, block=True, cancel=True)
            edit_card()
            assert evaluate("document.getElementById('f-start').value") == "10:00", "Cancelled move"
            evaluate("document.getElementById('form-cancel').click()")
            gesture(622, 652, block=True)
            wait_for("document.getElementById('status').textContent.startsWith('Saved')")
            gesture(674, 704, block=True)
            wait_for("document.getElementById('status').textContent.startsWith('Saved')")
            evaluate("document.querySelector('.block').dispatchEvent(new MouseEvent('contextmenu', "
                     "{bubbles:true, clientX:100, clientY:100}))")
            assert evaluate("!document.getElementById('block-context-menu').hidden")
            evaluate("window.__beforeCalendarReload=true")
            window.reload()
            wait_for("typeof window.__beforeCalendarReload === 'undefined' && "
                     "document.querySelector('.block')")
            edit_card()
            assert evaluate("document.getElementById('f-start').value") == "10:30"
            assert evaluate("document.getElementById('f-end').value") == "11:45"
            assert evaluate("document.querySelectorAll('.block').length") == 1
            print("PASS: DOM create, cancel, pointer ownership, move, resize, edit, context and reload")
        elif case == "completion":
            submit_identity("completion_student", "register")
            add_item("assignments", "document.getElementById('f-title').value='Essay';"
                     "document.getElementById('f-energy').value='high';", days=[0])
            wait_for("document.getElementById('status').textContent.startsWith('Saved')")
            evaluate("document.getElementById('solve').click()")
            wait_for("document.querySelector('.flex-block')")
            evaluate("document.querySelector('.flex-block').dispatchEvent("
                     "new MouseEvent('dblclick', {bubbles:true}))")
            evaluate("""document.getElementById('f-completed').checked=true;
                document.querySelector('#block-form button[type=submit]').click();""")
            wait_for("document.getElementById('status').textContent.startsWith('Saved')")
            evaluate("window.__beforeCompletionReload=true")
            window.reload()
            wait_for("typeof window.__beforeCompletionReload === 'undefined' && "
                     "document.getElementById('planner') && !document.getElementById('planner').hidden")
            assert evaluate("document.querySelectorAll('.flex-block').length") == 1, "Completed slot was lost"
            evaluate("document.getElementById('solve').click()")
            wait_for("!document.getElementById('debug').hidden")
            assert evaluate("document.querySelectorAll('.flex-block').length") == 1
            assert evaluate("document.querySelector('.flex-block').style.top") == "0rem"
            assert evaluate("document.querySelector('.flex-block').classList.contains('is-completed')")
            print("PASS: completing through the editor preserves spent work through save, reload and solve")
        elif case == "phase6":
            submit_identity("phase6_student", "register")
            add_item("class", "document.getElementById('f-title').value='School';"
                     "document.getElementById('f-start').value='06:00';"
                     "document.getElementById('f-end').value='23:00';", days=[0])
            wait_for("document.getElementById('status').textContent.startsWith('Saved')")
            add_item("assignments", "document.getElementById('f-title').value='Homework';"
                     "document.getElementById('f-energy').value='high';"
                     "document.getElementById('f-due-date').value=dateForDay(selectedWeek, 1);"
                     "document.getElementById('f-due-time').value='09:00';", days=[0, 1])
            wait_for("document.getElementById('status').textContent.startsWith('Saved')")
            evaluate("document.getElementById('solve').click()")
            wait_for("document.querySelector('.slack-tight')")
            evaluate(
                "document.querySelector('.block:not(.flex-block)')"
                ".dispatchEvent(new MouseEvent('dblclick', {bubbles: true}))"
            )
            assert evaluate("!document.getElementById('form-missed').hidden")
            evaluate("document.getElementById('form-missed').click()")
            wait_for("!document.getElementById('debug-changes').hidden")
            wait_for("document.getElementById('status').textContent.startsWith('Saved')")
            changes = evaluate("document.getElementById('debug-moves').textContent")
            assert "Tue 06:00 → Mon 06:00" in changes, changes
            # Room to spare gets no badge on the grid; its sentence stays in the Solve results.
            assert not evaluate("Boolean(document.querySelector('.slack-badge'))")
            assert evaluate("document.getElementById('debug-unplaced').textContent.includes('Room:')")
            evaluate("window.__beforeMissReload=true")
            window.reload()
            wait_for(
                "typeof window.__beforeMissReload === 'undefined' && document.getElementById('planner') && "
                "!document.getElementById('planner').hidden"
            )
            assert evaluate("document.querySelectorAll('.missed-block').length") == 1
            evaluate("document.getElementById('solve').click()")
            wait_for("!document.getElementById('debug-changes').hidden")
            evaluate("document.querySelector('#debug-moves .detail-button').click()")
            assert evaluate("document.getElementById('form-missed').textContent === 'Restore Mon'")
            evaluate("document.getElementById('form-missed').click()")
            wait_for("document.getElementById('status').textContent.startsWith('Saved')")
            evaluate("window.__beforeRestoreReload=true")
            window.reload()
            wait_for(
                "typeof window.__beforeRestoreReload === 'undefined' && "
                "document.getElementById('planner') && "
                "!document.getElementById('planner').hidden"
            )
            assert evaluate("document.querySelectorAll('.missed-block').length") == 0
            assert evaluate("document.querySelectorAll('.block:not(.flex-block)').length") == 1
            print("PASS: explanations, slack, one-day miss recovery, move list and restore in desktop")
        elif case == "stage1":
            submit_identity("stage1_student", "register")
            evaluate("document.getElementById('setup-close').click()")

            def fetch_json(path: str) -> Any:
                evaluate(f"window.__reply = undefined; api({json.dumps(path)})"
                         ".then(data => { window.__reply = JSON.stringify(data); })")
                wait_for("typeof window.__reply === 'string'")
                return json.loads(evaluate("window.__reply"))

            this_week = evaluate("selectedWeek")
            next_week = evaluate("shiftWeek(selectedWeek, 1)")
            homework_path = f"/api/assignments?week_start={this_week}&include_completed=true"
            week_path = f"/api/week?week_start={this_week}"
            due = evaluate("dateForDay(shiftWeek(selectedWeek, 1), 2)") + "T21:00"
            add_item("assignments", "document.getElementById('f-title').value='Essay';"
                     f"document.getElementById('f-due-date').value={json.dumps(due[:10])};"
                     "document.getElementById('f-due-time').value='21:00';", days=[0])
            wait_for("document.getElementById('status').textContent.startsWith('Saved')")
            homework = fetch_json(homework_path)["assignments"]
            assert [(item["title"], item["due"]) for item in homework] == [("Essay", due)], homework
            assignment_id = homework[0]["id"]
            session = fetch_json(week_path)["blocks"][0]
            assert session["assignment_id"] == assignment_id and session.get("latest") is None, session

            evaluate("document.getElementById('solve').click()")
            wait_for("!document.getElementById('debug').hidden")
            stats = evaluate("document.getElementById('debug-stats').textContent")
            assert stats == "1 task fits.", stats

            evaluate(f"deleteBlockById({json.dumps(session['id'])})")
            wait_for("document.getElementById('delete-dialog').open")
            evaluate("document.getElementById('delete-assignment').click()")
            wait_for("document.getElementById('status').textContent.startsWith('Deleted Essay')")
            assert fetch_json(homework_path)["assignments"] == []
            assert fetch_json(week_path)["blocks"] == []
            evaluate("document.getElementById('undo').click()")
            wait_for("document.getElementById('status').textContent === 'Undid deleting Essay.'")
            assert [item["id"] for item in fetch_json(homework_path)["assignments"]] == [assignment_id]
            assert [block["id"] for block in fetch_json(week_path)["blocks"]] == [session["id"]]

            evaluate("document.getElementById('undo').click()")
            wait_for("document.getElementById('status').textContent === 'Undid your last change.'")
            assert fetch_json(homework_path)["assignments"] == []
            assert fetch_json(week_path)["blocks"] == []
            evaluate("document.getElementById('redo').click()")
            wait_for("document.getElementById('status').textContent === 'Redid your last change.'")
            assert [item["id"] for item in fetch_json(homework_path)["assignments"]] == [assignment_id]

            evaluate("window.__file = exportWeekPayload(selectedWeek, weekState().blocks)")
            assert evaluate("window.__file.version") == 2
            evaluate(f"selectWeek({json.dumps(next_week)})")
            wait_for(f"selectedWeek === {json.dumps(next_week)} && !saving")
            evaluate(f"""window.__imported = undefined;
                window.__file.week_start = {json.dumps(next_week)};
                window.__file.assignments[0].title = 'Essay copy';
                importPayloadIntoWeek(parseImportPayload(JSON.stringify(window.__file)))
                    .then(ok => {{ window.__imported = ok; }});""")
            wait_for("window.__imported !== undefined")
            status = evaluate("document.getElementById('status').textContent")
            assert evaluate("window.__imported") is True, status
            copy_id = migrated_assignment_id(next_week, assignment_id)
            assignment_path = f"/api/assignments?week_start={next_week}&include_completed=true"
            stored = fetch_json(assignment_path)["assignments"]
            assert sorted((item["id"], item["title"]) for item in stored) == sorted(
                [(assignment_id, "Essay"), (copy_id, "Essay copy")]
            ), stored
            imported = fetch_json(f"/api/week?week_start={next_week}")["blocks"]
            assert [block["assignment_id"] for block in imported] == [copy_id], imported
            print("PASS: homework saves as an assignment, Solve, whole-homework delete and undo, "
                  "undo and redo of adding it, and a format 2 import into another week")
        elif case == "stage2":
            # At 390px the day agenda comes first and the whole path runs without a context menu.
            window.resize(390, 800)
            QTest.qWait(100)
            submit_identity("stage2_student", "register")
            evaluate("document.getElementById('setup-close').click()")
            assert evaluate("plannerView") == "day", "A 390px window did not start on the day agenda"
            assert not evaluate("document.getElementById('day-agenda').hidden")
            add_rect = "document.getElementById('add-homework').getBoundingClientRect()"
            on_screen = evaluate(f"{add_rect}.width > 0 && {add_rect}.right <= window.innerWidth")
            assert on_screen, "Add homework is off screen"

            def click_agenda(label: str) -> None:
                evaluate("Array.from(document.querySelectorAll('#day-agenda .agenda-row button'))"
                         f".find(b => b.textContent === {json.dumps(label)}).click()")

            tomorrow = evaluate("addDaysIso(currentDateInfo().iso, 1)")
            evaluate("document.getElementById('add-homework').click()")
            wait_for("document.getElementById('homework-dialog').open")
            evaluate(f"""document.getElementById('hw-title').value='Essay';
                document.getElementById('hw-due-date').value={json.dumps(tomorrow)};
                document.getElementById('hw-due-time').value='23:59';
                document.getElementById('hw-estimate').value='60';
                document.querySelector('#homework-form button[type=submit]').click();""")
            wait_for("document.getElementById('status').textContent.startsWith('Added Essay')")
            due_soon = (
                "Array.from(document.querySelectorAll('#day-agenda .agenda-section')).some(s => "
                "s.querySelector('h3').textContent === 'Due soon' && s.textContent.includes('Essay'))"
            )
            wait_for(due_soon)
            evaluate("document.getElementById('solve').click()")
            wait_for("!document.getElementById('debug').hidden")
            assert evaluate("document.getElementById('solve-label').textContent") == "Update my plan"
            click_agenda("Start focus")
            wait_for("!document.getElementById('focus-panel').hidden")
            evaluate("document.getElementById('focus-reset').click()")
            click_agenda("Finished")
            wait_for("document.getElementById('status').textContent.startsWith('Finished Essay')")
            # Pass the reply back as JSON text; runJavaScript does not hand arrays to Python reliably.
            evaluate("window.__done = undefined; "
                     "api('/api/assignments?week_start=' + selectedWeek + '&include_completed=true')"
                     ".then(data => { window.__done = JSON.stringify("
                     "data.assignments.map(a => a.completed)); })")
            wait_for("typeof window.__done === 'string'")
            done = json.loads(evaluate("window.__done"))
            assert done == [True], done

            # At 1280px Week still shows seven days, one control away, with Add homework on screen.
            window.resize(1280, 800)
            QTest.qWait(100)
            evaluate("document.getElementById('view-week').click()")
            wait_for("!document.getElementById('week').hidden")
            assert evaluate("document.querySelectorAll('.day-head').length") == 7
            assert evaluate("document.getElementById('add-homework').getBoundingClientRect().width > 0")
            assert evaluate("document.querySelector('.week-nav #export-week') === null")
            print("PASS: 390px day agenda, Add homework, plan, start focus and finish without "
                  "a context menu; 1280px week of seven days")
        elif case == "stage3":
            submit_identity("stage3_student", "register")
            evaluate("document.getElementById('setup-close').click()")
            add_item("class", "document.getElementById('f-title').value='School';", days=[0])
            wait_for("document.getElementById('status').textContent.startsWith('Saved')")

            # Copy one occurrence through the shared preview and persist it through
            # the real atomic API. The source block remains a separate Monday item.
            evaluate("""window.__stage3Done=undefined;
                const source=weekState().blocks.find(block => block.title === 'School');
                copyBlockById(source.id, 0, 'occurrence');
                pasteStage3Clipboard(1, source.start);
                confirmStage3Preview().then(ok => { window.__stage3Done=ok; });""")
            wait_for("window.__stage3Done !== undefined")
            assert evaluate("window.__stage3Done") is True
            assert evaluate("weekState().blocks.filter(block => block.title === 'School').length") == 2

            # Save the current fixed commitments as a routine, then apply only
            # Monday to next week. Applying snapshots the account first.
            evaluate(
                "window.__routineOpen=undefined; "
                "openRoutineDialog().then(ok => { window.__routineOpen=ok; })"
            )
            wait_for("window.__routineOpen !== undefined")
            evaluate("""document.getElementById('routine-name').value='School week';
                window.__routineSaved=undefined;
                saveNewRoutine().then(ok => { window.__routineSaved=ok; });""")
            wait_for("window.__routineSaved !== undefined")
            assert evaluate("window.__routineSaved") is True
            next_week = evaluate("shiftWeek(selectedWeek, 1)")
            evaluate(f"""document.getElementById('routine-destination').value={json.dumps(next_week)};
                [0,1,2,3,4,5,6].forEach(day => document.getElementById('routine-day-'+day).checked=day===0);
                window.__routineApplied=undefined;
                applyRoutine(Array.from(stage3Routines.keys())[0]).then(ok => {{
                    if (!ok) window.__routineApplied=false;
                    else confirmStage3Preview().then(saved => {{ window.__routineApplied=saved; }});
                }});""")
            wait_for("window.__routineApplied !== undefined")
            assert evaluate("window.__routineApplied") is True
            assert evaluate("selectedWeek") == next_week
            assert evaluate("weekState().blocks.length") == 1

            evaluate("window.__points=undefined; api('/api/restore-points').then(data => { "
                     "window.__points=JSON.stringify(data.restore_points); })")
            wait_for("typeof window.__points === 'string'")
            points = json.loads(evaluate("window.__points"))
            assert len(points) == 1, points
            assert points[0]["label"].startswith("Before applying School week"), points

            # Restore the pre-apply snapshot. It removes the destination week,
            # clears ephemeral clipboard/history, and leaves the saved routine.
            point_id = points[0]["id"]
            evaluate(f"window.__restorePreview=undefined; previewRestorePoint({json.dumps(point_id)})"
                     ".then(ok => {{ window.__restorePreview=ok; }})")
            wait_for("window.__restorePreview !== undefined")
            assert evaluate("window.__restorePreview") is True
            evaluate(
                "window.__restored=undefined; "
                "restoreFromPreview().then(ok => { window.__restored=ok; })"
            )
            wait_for("window.__restored !== undefined", timeout=20)
            assert evaluate("window.__restored") is True
            evaluate(f"window.__nextWeek=undefined; api('/api/week?week_start={next_week}')"
                     ".then(data => {{ window.__nextWeek=JSON.stringify(data.blocks); }})")
            wait_for("typeof window.__nextWeek === 'string'")
            assert json.loads(evaluate("window.__nextWeek")) == []
            assert evaluate("stage3Clipboard === null && undoSteps.length === 0")
            evaluate("window.__routines=undefined; api('/api/routines').then(data => { "
                     "window.__routines=JSON.stringify(data.routines); })")
            wait_for("typeof window.__routines === 'string'")
            assert len(json.loads(evaluate("window.__routines"))) == 1

            # A retried batch with the same operation id stores once and replays the first answer.
            evaluate("""window.__retry=undefined;
                const retryBody=JSON.stringify({weeks:[{week_start:selectedWeek,
                    blocks:weekState().blocks.concat([{id:'b-probe-retry',kind:'locked',title:'Retry',
                        duration_min:30,days:[2],start:'18:00'}]),
                    revision:weekState().revision}], assignments:[], operation_id:'probe-retry-operation'});
                api('/api/changes',{method:'POST',body:retryBody}).then(first =>
                    api('/api/changes',{method:'POST',body:retryBody}).then(second => {
                        window.__retry=JSON.stringify([first.weeks[0].revision, second.weeks[0].revision,
                            second.weeks[0].blocks.filter(block => block.title === 'Retry').length]);
                    }));""")
            wait_for("typeof window.__retry === 'string'")
            retried = json.loads(evaluate("window.__retry"))
            assert retried[0] == retried[1] and retried[2] == 1, retried

            # Routines and restore points survive a reload, including the recovery point the restore kept.
            evaluate("window.__beforeStage3Reload=true")
            window.reload()
            wait_for(
                "typeof window.__beforeStage3Reload === 'undefined' && "
                "document.getElementById('planner') && !document.getElementById('planner').hidden"
            )
            assert len(api_json("/api/routines")["routines"]) == 1
            labels = [point["label"] for point in api_json("/api/restore-points")["restore_points"]]
            assert len(labels) == 2 and labels[0].startswith("Before restore"), labels

            # Another account sees none of it, and the first account's restore point is not found for it.
            evaluate("document.getElementById('logout').click()")
            wait_for("!document.getElementById('login-screen').hidden")
            submit_identity("stage3_other", "register")
            evaluate("document.getElementById('setup-close').click()")
            assert api_json("/api/routines")["routines"] == []
            assert api_json("/api/restore-points")["restore_points"] == []
            assert api_json(f"/api/restore-points/{point_id}/preview") == {"status": 404}
            evaluate("document.getElementById('logout').click()")
            wait_for("!document.getElementById('login-screen').hidden")
            submit_identity("stage3_student", "login")
            assert len(api_json("/api/routines")["routines"]) == 1
            print(
                "PASS: copy preview, routine save/apply, automatic restore point, restore, a retried "
                "operation, reload and a second account through real APIs"
            )
        elif case == "stage3_mobile":
            # A phone-width dark window carries unfinished homework into next week exactly once.
            window.resize(390, 800)
            QTest.qWait(100)
            submit_identity("stage3_phone", "register")
            evaluate("document.getElementById('setup-close').click()")
            evaluate(
                "document.getElementById('theme').value='nocturne'; "
                "document.getElementById('theme').dispatchEvent(new Event('change'))"
            )
            wait_for("!document.getElementById('theme').disabled")
            assert page_theme() == "nocturne"
            due = evaluate("dateForDay(shiftWeek(selectedWeek, 1), 2)")
            evaluate("document.getElementById('add-homework').click()")
            wait_for("document.getElementById('homework-dialog').open")
            evaluate(f"""document.getElementById('hw-title').value='Essay';
                document.getElementById('hw-due-date').value={json.dumps(due)};
                document.getElementById('hw-due-time').value='23:59';
                document.getElementById('hw-estimate').value='60';
                document.querySelector('#homework-form button[type=submit]').click();""")
            wait_for("document.getElementById('status').textContent.startsWith('Added Essay')")
            assignment_id = evaluate("Array.from(assignments.keys())[0]")
            next_week = evaluate("shiftWeek(selectedWeek, 1)")
            evaluate(f"selectWeek({json.dumps(next_week)})")
            wait_for(f"selectedWeek === {json.dumps(next_week)} && !saving")
            wait_for("!document.getElementById('unfinished-review').hidden")
            assert evaluate("document.querySelectorAll('#unfinished-list li').length") == 1
            evaluate("document.querySelector('#unfinished-list button').click()")
            wait_for("document.getElementById('stage3-preview-dialog').open")
            confirm_rect = "document.getElementById('stage3-preview-confirm').getBoundingClientRect()"
            assert evaluate(f"{confirm_rect}.height >= 44"), "The preview's save button is under 44px"
            fits = evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            assert fits, "Preview overflows at 390px"
            evaluate("document.getElementById('stage3-preview-confirm').click()")
            wait_for("document.getElementById('status').textContent.startsWith('Saved unfinished homework')")
            assert evaluate("document.querySelectorAll('#unfinished-list li').length") == 0
            week = api_json(f"/api/week?week_start={next_week}")
            sessions = [block for block in week["blocks"] if block.get("assignment_id") == assignment_id]
            assert len(sessions) == 1, week["blocks"]
            homework_path = f"/api/assignments?week_start={next_week}&include_completed=true"
            homework = api_json(homework_path)["assignments"]
            kept = [(item["id"], item["due"]) for item in homework]
            assert kept == [(assignment_id, due + "T23:59")], homework
            print("PASS: at 390px in the dark theme, unfinished homework goes into next week once, "
                  "keeping its id and deadline")
        elif case == "stage4":
            submit_identity("stage4_student", "register")
            evaluate("document.getElementById('setup-close').click()")
            add_item(
                "class",
                "document.getElementById('f-title').value='School';",
                days=[0, 1, 2, 3, 4],
            )
            wait_for("document.getElementById('status').textContent.startsWith('Saved')")
            due = evaluate("dateForDay(shiftWeek(selectedWeek, 1), 4)")
            evaluate("document.getElementById('add-homework').click()")
            wait_for("document.getElementById('homework-dialog').open")
            evaluate(f"""document.getElementById('hw-title').value='Essay';
                document.getElementById('hw-due-date').value={json.dumps(due)};
                document.getElementById('hw-due-time').value='23:59';
                document.getElementById('hw-estimate').value='240';
                document.querySelector('#homework-form button[type=submit]').click();""")
            wait_for("document.getElementById('status').textContent.startsWith('Added Essay')")
            assignment_id = evaluate("Array.from(assignments.keys())[0]")
            evaluate(
                "weekState().blocks = weekState().blocks.filter(function (block) {"
                " return !block.assignment_id; });"
                " weekState().dirty = true;"
            )
            evaluate("window.__cleared=undefined; saveWeek().then(ok => { window.__cleared=ok; })")
            wait_for("window.__cleared === true")
            evaluate(f"""window.__spread=undefined;
                openHomeworkDialog({json.dumps(assignment_id)});
                openSpreadDialog({json.dumps(assignment_id)});
                document.getElementById('spread-session').value='60';
                document.getElementById('spread-from').value=todayIso();
                previewSpread().then(ok => {{ window.__spread=ok; }});""")
            wait_for("window.__spread !== undefined")
            spread_error = evaluate("document.getElementById('spread-error').textContent")
            assert evaluate("window.__spread") is True, spread_error
            evaluate(
                "window.__spreadSaved=undefined; "
                "confirmStage3Preview().then(ok => { window.__spreadSaved=ok; })"
            )
            wait_for("window.__spreadSaved !== undefined")
            assert evaluate("window.__spreadSaved") is True
            sessions_before = evaluate(
                "weekState().blocks.filter(block => block.assignment_id).length"
            )
            assert sessions_before >= 1

            evaluate("""window.__late=undefined;
                const noon=new Date(); noon.setHours(12,0,0,0);
                if (!openRunningLate(noon)) window.__late=false;
                else previewRunningLate(noon).then(ok => { window.__late=ok; });""")
            wait_for("window.__late !== undefined")
            late_error = evaluate(
                "document.getElementById('late-error').textContent"
                " || document.getElementById('status').textContent"
            )
            assert evaluate("window.__late") is True, late_error
            evaluate(
                "window.__accepted=undefined; "
                "acceptRunningLate().then(ok => { window.__accepted=ok; })"
            )
            wait_for("window.__accepted !== undefined", timeout=20)
            assert evaluate("window.__accepted") is True
            late_kept = "weekState().blocks.filter(block => block.title === 'Running late').length"
            school_kept = "weekState().blocks.filter(block => block.title === 'School').length"
            work_kept = "weekState().blocks.filter(block => block.assignment_id).length"
            assert evaluate(late_kept) == 1
            assert evaluate(school_kept) == 1
            assert evaluate(work_kept) >= sessions_before
            evaluate("window.__beforeStage4Reload=true")
            window.reload()
            wait_for(
                "typeof window.__beforeStage4Reload === 'undefined' && "
                "document.getElementById('planner') && !document.getElementById('planner').hidden"
            )
            assert evaluate(late_kept) == 1
            assert evaluate(school_kept) == 1
            print(
                "PASS: spread four hours, run 30 minutes late, keep school and homework, "
                "reload keeps the late interval"
            )
        elif case == "stage5":
            submit_identity("comfort_student", "register")
            evaluate("document.getElementById('setup-close').click()")
            evaluate("document.getElementById('prefs-open').click()")
            wait_for("document.getElementById('prefs-dialog').open")
            evaluate("document.getElementById('settings-focus').open=true")
            wait_for("document.querySelectorAll('#reminder-limits li').length === 4")
            evaluate("""document.getElementById('pref-timer-work').value='25';
                document.getElementById('pref-timer-break').value='5';
                document.getElementById('timer-preview').click();""")
            wait_for("!document.getElementById('timer-preview-result').hidden")
            assert "becomes 30" in evaluate("document.getElementById('timer-preview-message').textContent")
            assert "120 min on the calendar" in evaluate(
                "document.getElementById('timer-preview-segments').textContent"
            )
            evaluate("document.getElementById('timer-use-rounded').click()")
            assert evaluate("document.getElementById('pref-timer-work').value") == "30"
            assert evaluate("document.getElementById('pref-timer-break').value") == "15"

            # Preview uses the unsaved sound controls and does not make an HTTP request or
            # spend a real reminder's once-per-start key.
            evaluate("""window.__stage5Fetch=fetch; window.__stage5Fetches=0;
                fetch=function(){window.__stage5Fetches += 1;
                    return window.__stage5Fetch.apply(this, arguments);};
                window.__stage5Sound=soundOnce; window.__stage5Sounds=0;
                soundOnce=function(){window.__stage5Sounds += 1;};
                document.getElementById('pref-reminder-sound').checked=true;
                document.getElementById('pref-alert-volume').value='0';
                document.getElementById('test-reminder').click();""")
            assert evaluate("window.__stage5Fetches") == 0
            assert evaluate("window.__stage5Sounds") == 0
            assert evaluate("firedReminders.size") == 0
            evaluate("""document.getElementById('pref-alert-volume').value='42';
                document.getElementById('preview-alert').click();""")
            assert evaluate("window.__stage5Sounds") == 1
            evaluate("fetch=window.__stage5Fetch; soundOnce=window.__stage5Sound")

            evaluate("""document.getElementById('pref-end-chime').checked=true;
                document.getElementById('pref-tray-notifications').checked=false;
                document.getElementById('pref-start-at-login').checked=true;
                document.getElementById('pref-preferred-view').value='day';
                document.getElementById('pref-auto-split').checked=true;
                document.getElementById('prefs-save').click();""")
            wait_for("!document.getElementById('prefs-dialog').open")
            evaluate("document.getElementById('sidebar-toggle').click()")
            wait_for("!layoutSaveRunning")

            evaluate("window.__stage5BeforeReload=true")
            window.reload()
            wait_through_reload(
                "typeof window.__stage5BeforeReload === 'undefined' && "
                "document.getElementById('account-name').textContent === 'comfort_student'"
            )
            assert evaluate("plannerView") == "day"
            assert evaluate("prefs.alert_volume") == 42
            assert evaluate("prefs.end_chime") is True
            assert evaluate("prefs.tray_notifications") is False
            assert evaluate("prefs.start_at_login") is True
            assert evaluate("prefs.sidebar_collapsed") is True
            assert evaluate("getComputedStyle(document.getElementById('planner-sidebar')).display") == "none"

            window.resize(390, 800)
            QTest.qWait(100)
            assert evaluate("getComputedStyle(document.getElementById('planner-sidebar')).display") == "block"
            assert evaluate("getComputedStyle(document.getElementById('sidebar-resizer')).display") == "none"
            assert evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            print(
                "PASS: settings groups, timer rounding, local silent preview, comfort save, "
                "remembered day view and responsive sidebar"
            )
        elif case == "stage6":
            codes = submit_identity("access_student", "register", acknowledge_codes=False)
            assert len(codes) == 8
            assert evaluate("Object.hasOwn(account, 'recovery_codes')") is False
            assert evaluate("document.getElementById('setup-dialog').open") is False
            evaluate("""document.getElementById('recovery-codes-ack').checked=true;
                document.getElementById('recovery-codes-ack').dispatchEvent(new Event('change'));
                document.getElementById('recovery-codes-done').click();""")
            wait_for("document.getElementById('setup-dialog').open")
            evaluate("document.getElementById('setup-close').click()")

            evaluate("document.getElementById('prefs-open').click()")
            wait_for("document.getElementById('account-location-label').textContent === 'On this device'")
            wait_for(
                "document.getElementById('recovery-status').textContent === "
                "'8 unused recovery codes remain.'"
            )
            assert evaluate("document.getElementById('prefs-account').textContent") == (
                "Signed in as access_student"
            )
            assert evaluate("document.getElementById('recovery-status').textContent") == (
                "8 unused recovery codes remain."
            )
            evaluate("document.getElementById('change-password-open').click()")
            evaluate("""document.getElementById('change-password-current').value='temporary-test-password';
                document.getElementById('change-password-new').value='changed-test-password';
                document.getElementById('change-password-confirm').value='changed-test-password';
                document.querySelector('#change-password-form button[type=submit]').click();""")
            wait_for("document.getElementById('status').textContent.includes('Password changed')")

            evaluate("document.getElementById('logout').click()")
            wait_for("document.getElementById('planner').hidden")
            evaluate("document.getElementById('show-recover').click()")
            evaluate(f"""document.getElementById('recover-username').value='access_student';
                document.getElementById('recover-code').value={json.dumps(codes[0])};
                document.getElementById('recover-password').value='recovered-test-password';
                document.getElementById('recover-password-confirm').value='recovered-test-password';
                document.querySelector('#recover-form button[type=submit]').click();""")
            wait_for("document.getElementById('status').textContent.includes('Account recovered')")
            assert evaluate("document.getElementById('account-name').textContent") == "access_student"

            add_item("class", "document.getElementById('f-title').value='School';", days=[0])
            wait_for("document.getElementById('status').textContent.startsWith('Saved')")
            evaluate("""window.__stage6Snapshot=null; window.__stage6Download=downloadText;
                downloadText=function(_name, body){window.__stage6Snapshot=JSON.parse(body);};
                document.getElementById('prefs-open').click();
                document.getElementById('transfer-open').click();
                document.getElementById('account-export-password').value='recovered-test-password';
                document.querySelector('#account-export-form button[type=submit]').click();""")
            wait_for("window.__stage6Snapshot !== null")
            snapshot = cast(dict[str, Any], json.loads(evaluate("JSON.stringify(window.__stage6Snapshot)")))
            assert snapshot["username"] == "access_student"
            assert len(cast(list[Any], snapshot["weeks"])) == 1
            evaluate(
                "downloadText=window.__stage6Download; "
                "document.getElementById('transfer-close').click()"
            )

            evaluate("document.getElementById('logout').click()")
            wait_for("document.getElementById('planner').hidden")
            submit_identity("destination_student", "register")
            evaluate("document.getElementById('setup-close').click()")
            evaluate(
                "document.getElementById('prefs-open').click(); "
                "document.getElementById('transfer-open').click()"
            )
            evaluate("previewTransferSnapshot(" + json.dumps(snapshot) + ")")
            wait_for("!document.getElementById('account-import-preview').hidden")
            assert evaluate("document.getElementById('account-import-source').textContent").startswith(
                "From access_student."
            )
            evaluate("""document.getElementById('account-import-ack').checked=true;
                document.getElementById('account-import-ack').dispatchEvent(new Event('change'));
                document.getElementById('account-import-confirm').click();""")
            wait_for("document.getElementById('status').textContent.includes('Account data imported')")
            assert evaluate("document.querySelectorAll('.block').length") == 1
            assert evaluate("document.querySelector('.block').textContent.includes('School')") is True

            evaluate("document.getElementById('prefs-open').click()")
            wait_for("document.getElementById('account-location-label').textContent === 'On this device'")
            evaluate("document.getElementById('delete-account-open').click()")
            evaluate("""document.getElementById('delete-account-username').value='destination_student';
                document.getElementById('delete-account-password').value='temporary-test-password';
                document.querySelector('#delete-account-form button[type=submit]').click();""")
            wait_for("document.getElementById('status').textContent.includes('Account deleted')")
            assert evaluate("!document.getElementById('register-screen').hidden") is True
            print(
                "PASS: one-time codes, password change, recovery, local identity, "
                "previewed transfer and deletion"
            )
        elif case == "stage7_month":
            submit_identity("month_student", "register")
            evaluate("document.getElementById('setup-close').click()")
            assignment = {
                "id": "month-project", "title": "History essay", "course": "History",
                "category": "Homework", "priority": 3, "energy": "medium", "spotify_url": None,
                "due": "2026-09-16T23:59", "estimate_min": 120, "focus_minutes": 0,
                "focus_sessions": 0, "completed": False, "completed_at": None, "revision": 0,
                "notes": "Private outline", "links": [{"label": "Sources", "url": "https://example.test"}],
                "checklist": [{"id": "draft", "text": "Draft", "done": True}],
            }
            overdue = {
                **assignment, "id": "late-lab", "title": "Late lab", "course": "Science",
                "due": "2026-08-15T17:00", "estimate_min": 45, "notes": "", "links": [],
                "checklist": [],
            }
            sessions = [
                {"id": "essay-tue", "title": "History essay", "kind": "flexible",
                 "duration_min": 60, "days": [1], "priority": 3, "energy": "medium",
                 "start": "16:00", "assignment_id": "month-project", "category": "Homework"},
                {"id": "essay-wed", "title": "History essay", "kind": "flexible",
                 "duration_min": 60, "days": [2], "priority": 3, "energy": "medium",
                 "start": "16:00", "assignment_id": "month-project", "category": "Homework"},
            ]
            assignment_json = json.dumps(assignment)
            overdue_json = json.dumps(overdue)
            sessions_json = json.dumps(sessions)
            evaluate(f"""window.__monthSeeded=false;
                (async function(){{
                    await api('/api/assignments/month-project',
                        {{method:'PUT', body:JSON.stringify({assignment_json})}});
                    await api('/api/assignments/late-lab',
                        {{method:'PUT', body:JSON.stringify({overdue_json})}});
                    await api('/api/week', {{method:'PUT', body:JSON.stringify({{
                        week_start:'2026-09-14', blocks:{sessions_json}, revision:0
                    }})}});
                    window.__monthSeeded=true;
                }})().catch(error => {{window.__monthSeedError=error.message;}});""")
            wait_for("window.__monthSeeded || window.__monthSeedError")
            assert evaluate("window.__monthSeedError || ''") == ""
            evaluate(
                "selectedDay='2026-09-16'; plannerView='day'; "
                "document.getElementById('view-month').click()"
            )
            wait_for("plannerView === 'month' && monthSnapshot && monthSnapshot.month === '2026-09'")
            assert evaluate("document.getElementById('week-label').textContent") == "September 2026"
            assert evaluate(
                "document.querySelector('.month-day[data-date=\"2026-09-16\"]')"
                ".textContent.includes('History essay')"
            )
            assert evaluate(
                "document.getElementById('month-projects').textContent"
                ".includes('Checklist 1/1 · Notes · Links')"
            )
            assert evaluate("document.getElementById('month-overdue').textContent.includes('Late lab')")
            assert evaluate(
                "!document.getElementById('month-projects').textContent.includes('Private outline')"
            )
            assert evaluate("getComputedStyle(document.getElementById('planner-sidebar')).display") == "none"

            for width in (1280, 390):
                window.resize(width, 800)
                QTest.qWait(150)
                assert evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (
                    f"Month overflow at {width}px"
                )
                assert evaluate(
                    "document.querySelector('.month-day[data-date=\"2026-09-16\"]')"
                    ".getBoundingClientRect().height >= 44"
                ), f"Month date target is shorter than 44px at {width}px"
            evaluate("document.querySelector('.month-day[data-date=\"2026-09-16\"]').click()")
            wait_for("plannerView === 'day' && selectedDay === '2026-09-16'")
            assert evaluate("document.getElementById('week-label').textContent.includes('Wednesday')")
            print(
                "PASS: real month API data renders deadlines, project indicators and overdue work "
                "at 1280px and 390px, then opens Day"
            )
        elif case == "phase7":
            submit_identity("focus_student", "register")
            add_item("assignments", "document.getElementById('f-title').value='Maths';"
                     "document.getElementById('f-duration').value='60';", days=[0])
            wait_for("document.getElementById('status').textContent.startsWith('Saved')")
            evaluate("document.getElementById('solve').click()")
            wait_for("document.querySelector('.flex-block')")

            # Splitting writes children on one day and replaces the source, so a
            # task offered on several days must not be offered the split at all.
            # Use the task the solver actually placed, and change only its days.
            def split_hidden(days: str) -> object:
                return evaluate(
                    "(function(){var b=weekState().blocks.find(function(x)"
                    "{return x.kind==='flexible';});"
                    f"b.days={days};"
                    "showContextMenu(0, 0, b.id, b.days[0]);"
                    "var s=document.querySelector"
                    "('#block-context-menu button[data-action=split-pomodoros]');"
                    "return s ? s.hidden : 'missing';})()"
                )

            observed = split_hidden("[0]")
            assert observed is False, f"Split not offered for the placed one-day task (got {observed!r})"
            assert split_hidden("[0,2,4]") is True, (
                "Split offered for a task on several candidate days, which would drop the rest"
            )

            # A task only becomes focusable once the solver has given it a slot.
            wait_for("document.querySelector('#focus-tasks li button')")
            assert not evaluate("document.querySelector('#focus-tasks li button').disabled"), (
                "Focus stayed disabled for a placed task"
            )
            evaluate("document.querySelector('#focus-tasks li button').click()")
            wait_for("!document.getElementById('focus-panel').hidden")
            assert evaluate("document.getElementById('focus-time').textContent") != "00:00", (
                "Focus timer never started counting"
            )

            evaluate("document.getElementById('focus-pause').click()")
            paused = evaluate("document.getElementById('focus-time').textContent")
            QTest.qWait(1500)
            assert evaluate("document.getElementById('focus-time').textContent") == paused, (
                "Paused focus timer kept counting down"
            )

            phase = evaluate("document.getElementById('focus-phase').textContent")
            evaluate("document.getElementById('focus-skip').click()")
            wait_for(f"document.getElementById('focus-phase').textContent !== {json.dumps(phase)}")
            evaluate("document.getElementById('focus-reset').click()")
            wait_for("document.getElementById('focus-panel').hidden")

            evaluate("document.getElementById('prefs-open').click()")
            wait_for("document.getElementById('prefs-dialog').open")
            evaluate("""document.getElementById('alarm-name').value='Morning review';
                document.getElementById('alarm-time').value='07:30';
                document.getElementById('alarm-add').click();""")
            wait_for("document.querySelectorAll('#alarm-list li').length === 1")
            assert evaluate(
                "document.getElementById('now-next').hidden === "
                "(document.getElementById('now-next').textContent === '')"
            ), "Now / Next is shown empty or hidden with text"
            evaluate("document.getElementById('prefs-dialog').close()")

            print("PASS: focus timer, alarms and the preferences dialog work in a real browser")
        elif case == "download":
            submit_identity("draft_student", "register")
            server.stop()
            add_item("assignments", "document.getElementById('f-title').value='Offline draft';", days=[0])
            wait_for("document.getElementById('status').textContent.startsWith('Not saved')")
            destination = root / "draft.json"
            with patch("PySide6.QtWidgets.QFileDialog.getSaveFileName", return_value=(str(destination), "")):
                evaluate("document.getElementById('download-draft').click()")
                until = time.monotonic() + 5
                while not destination.exists() and time.monotonic() < until:
                    QTest.qWait(50)
                assert destination.exists(), "Desktop did not save the requested draft download"
                assert json.loads(destination.read_text())["blocks"][0]["title"] == "Offline draft"
            print("PASS: unsaved offline draft downloads through the desktop save dialog")
        elif case == "popup":
            with patch(
                "desktop.main.QDesktopServices.openUrl",
                side_effect=record_external,
            ):
                evaluate("""const link=document.createElement('a'); link.href='https://example.com/help';
                    link.target='_blank'; document.body.appendChild(link); link.click();""")
                until = time.monotonic() + 5
                while not opened and time.monotonic() < until:
                    QTest.qWait(50)
                assert opened == ["https://example.com/help"], opened
                assert window._stack.currentIndex() == 0
                # Popup pages must not remain alive loading content after handoff.
                QTest.qWait(100)
                pages = page.findChildren(QWebEnginePage)
                assert not pages, f"External popup retained {len(pages)} hidden browser page(s)"
            print("PASS: external popup handed off once without hidden page")
        elif case == "navigation":
            with patch(
                "desktop.main.QDesktopServices.openUrl",
                side_effect=record_external,
            ):
                for target in ("file:///tmp/private.txt", "javascript:alert(1)", "data:text/html,hello"):
                    accepted = page.acceptNavigationRequest(
                        QUrl(target), QWebEnginePage.NavigationType.NavigationTypeLinkClicked, True
                    )
                    assert not accepted
                assert opened == [], "Non-web links were sent to an OS handler"
                assert not page.acceptNavigationRequest(
                    QUrl("https://example.com/help"),
                    QWebEnginePage.NavigationType.NavigationTypeLinkClicked,
                    True,
                )
                assert opened == ["https://example.com/help"]
            print("PASS: web external links handed off, unsupported protocols blocked")
        elif case == "tray":
            assert window._tray_icon is not None
            assert not window._tray_icon.icon().isNull(), "Tray icon is blank, so the tray entry is invisible"
            assert window._tray_menu is not None
            assert [action.text() for action in window._tray_menu.actions() if not action.isSeparator()] == [
                "Open FlexWeek",
                "Quit",
            ]

            class FakePermission:
                def __init__(self, permission_type, permission_origin: str) -> None:
                    self._permission_type = permission_type
                    self._origin = QUrl(permission_origin)
                    self.granted = False
                    self.denied = False

                def permissionType(self):
                    return self._permission_type

                def origin(self):
                    return self._origin

                def grant(self) -> None:
                    self.granted = True

                def deny(self) -> None:
                    self.denied = True

            same_origin = FakePermission(QWebEnginePermission.PermissionType.Notifications, origin)
            page._handle_permission(cast(QWebEnginePermission, same_origin))
            assert same_origin.granted and not same_origin.denied
            foreign = FakePermission(
                QWebEnginePermission.PermissionType.Notifications, "https://example.com"
            )
            page._handle_permission(cast(QWebEnginePermission, foreign))
            assert foreign.denied and not foreign.granted
            unrelated = FakePermission(QWebEnginePermission.PermissionType.Geolocation, origin)
            page._handle_permission(cast(QWebEnginePermission, unrelated))
            assert unrelated.denied and not unrelated.granted

            messages: list[tuple[str, str, int]] = []
            # Captured rather than mocked: the real tray call would need a live desktop.
            window._tray_icon.supportsMessages = lambda: True  # type: ignore[method-assign]
            window._tray_icon.showMessage = (  # type: ignore[method-assign]
                lambda title, body, _icon=None, msecs=0: messages.append((title, body, msecs))
            )
            evaluate("Notification.requestPermission(); true")
            wait_for("Notification.permission === 'granted'")
            evaluate("window.__notice = new Notification('Focus finished', {body: 'Take a break'});")
            until = time.monotonic() + 5
            while not messages and time.monotonic() < until:
                QTest.qWait(50)
            assert messages == [("Focus finished", "Take a break", 10_000)], messages
            assert window._notification is not None
            evaluate(
                "window.__stay = new Notification('Stay', {body: 'Until handled', tag: 'flexweek-stay'});"
            )
            until = time.monotonic() + 5
            while len(messages) < 2 and time.monotonic() < until:
                QTest.qWait(50)
            assert messages[-1] == ("Stay", "Until handled", 0), messages
            assert window._notification is not None
            assert window._notification.tag() == "flexweek-stay"

            window.hide()
            window._on_tray_activated(QSystemTrayIcon.ActivationReason.Trigger)
            assert window.isVisible(), "Tray activation did not restore the window"
            close_event = QCloseEvent()
            window.closeEvent(close_event)
            assert not close_event.isAccepted()
            assert window.isHidden(), "Closing with a tray did not hide the window"
            assert messages[-1][0] == "FlexWeek is still running", messages
            window.restore_window()
            window.closeEvent(QCloseEvent())
            assert [title for title, _body, _ms in messages].count("FlexWeek is still running") == 1, messages
            window._on_notification_clicked()
            assert window.isVisible(), "Clicking a notification did not restore the window"
            assert window._notification is None
            window.quit_app()
            quit_event = QCloseEvent()
            window.closeEvent(quit_event)
            assert quit_event.isAccepted(), "Explicit Quit was intercepted as close-to-tray"
            print("PASS: notification permission, tray presentation, quick-open, close and quit")
        elif case == "no_icon":
            with patch("desktop.main.app_icon_path", return_value=root / "missing.png"):
                iconless = MainWindow(origin, tray_enabled=True)
            assert iconless._tray_icon is None, "Installed a tray entry that cannot be seen"
            iconless.show()
            close_event = QCloseEvent()
            iconless.closeEvent(close_event)
            assert close_event.isAccepted(), "Close hid the window with no visible tray to restore it"
            iconless.deleteLater()
            print("PASS: without a usable tray icon, closing the window closes the app")
        elif case == "instance":
            name = instance_name(str(root))
            assert not show_running_instance(name), "Found a running instance before one started"
            assert window.listen_for_instances(name)
            window.hide()
            assert show_running_instance(name), "Second launch could not reach the running app"
            until = time.monotonic() + 5
            while not window.isVisible() and time.monotonic() < until:
                QTest.qWait(50)
            assert window.isVisible(), "Second launch did not bring back the hidden window"
            print("PASS: a second launch shows the running window instead of starting another app")
        else:
            raise AssertionError(case)
    finally:
        window._view.setPage(QWebEnginePage(window._view))
        page.deleteLater()
        window.close()
        QTest.qWait(50)
        server.stop()
        app.quit()


if __name__ == "__main__":
    run(sys.argv[1], Path(sys.argv[2]))
