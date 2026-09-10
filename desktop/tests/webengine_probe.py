"""Isolated Qt integration probe, launched by test_webengine.py."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import cast
from unittest.mock import patch

from PySide6.QtCore import QEventLoop, QTimer, QUrl
from PySide6.QtGui import QCloseEvent
from PySide6.QtTest import QTest
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEnginePermission
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from desktop.main import MainWindow, instance_name, show_running_instance
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

    def submit_identity(name: str, action: str) -> None:
        evaluate(f"""if (document.getElementById('{action}-screen').hidden)
                document.getElementById('show-{action}').click();
            document.getElementById('{action}-username').value={json.dumps(name)};
            document.getElementById('{action}-password').value='temporary-test-password';
            document.querySelector('#{action}-form button[type=submit]').click();""")
        wait_for(f"document.getElementById('account-name').textContent === {json.dumps(name)}")
        wait_for("!document.getElementById('planner').hidden")

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
        assert evaluate("document.getElementById('login-screen').hidden"), "Log in shown on first launch"
        if case == "accounts":
            submit_identity("first_student", "register")
            add_item("class", "document.getElementById('f-title').value='School';", days=[0])
            wait_for("document.getElementById('status').textContent.startsWith('Saved')")
            assert evaluate("document.querySelectorAll('.block').length") == 1
            evaluate("document.getElementById('solve').click()")
            wait_for("!document.getElementById('debug').hidden")
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
            assert evaluate("document.documentElement.dataset.theme") == "slate"
            assert evaluate("document.querySelectorAll('.block').length") == 1
            evaluate("document.getElementById('logout').click()")
            wait_for("document.getElementById('planner').hidden")
            assert evaluate("document.querySelectorAll('.block').length") == 0
            submit_identity("second_student", "register")
            assert evaluate("document.querySelectorAll('.block').length") == 0
            assert evaluate("document.documentElement.dataset.theme") == "nocturne"
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
                     "document.getElementById('f-due-day').value='1';"
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
            assert evaluate("Boolean(document.querySelector('.slack-ok'))")
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
            assert evaluate("document.getElementById('now-next').textContent.trim().length") > 0, (
                "Now / Next line rendered empty"
            )
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
