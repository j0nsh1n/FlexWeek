"""Isolated Qt integration probe, launched by test_webengine.py."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QEventLoop, QTimer, QUrl
from PySide6.QtTest import QTest
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWidgets import QApplication

from desktop.main import MainWindow
from desktop.server import LocalServer


def run(case: str, root: Path) -> None:
    app = QApplication([])
    app.setApplicationName("FlexWeek-test")
    server = LocalServer(root / "account.db")
    origin = server.start()
    window = MainWindow(origin)
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
        evaluate(f"""document.getElementById('username').value={json.dumps(name)};
            document.getElementById('password').value='temporary-test-password';
            document.querySelector('button[value={action}]').click();""")
        wait_for(f"document.getElementById('account-name').textContent === {json.dumps(name)}")
        wait_for("!document.getElementById('planner').hidden")

    try:
        window.load_app()
        wait_for(
            "document.getElementById('status') && "
            "document.getElementById('status').textContent.includes('Sign in')"
        )
        if case == "accounts":
            submit_identity("first_student", "register")
            evaluate("""document.getElementById('add-locked').click();
                document.getElementById('f-title').value='School';
                document.querySelector('input[name=f-day][value="0"]').checked=true;
                document.querySelector('#block-form button[type=submit]').click();""")
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
        elif case == "phase6":
            submit_identity("phase6_student", "register")
            evaluate("""document.getElementById('add-locked').click();
                document.getElementById('f-title').value='School';
                document.getElementById('f-duration').value='1020';
                document.querySelector('input[name=f-day][value="0"]').checked=true;
                document.getElementById('f-start').value='06:00';
                document.querySelector('#block-form button[type=submit]').click();""")
            wait_for("document.getElementById('status').textContent.startsWith('Saved')")
            evaluate("""document.getElementById('add-flexible').click();
                document.getElementById('f-title').value='Homework';
                document.querySelector('input[name=f-day][value="0"]').checked=true;
                document.querySelector('input[name=f-day][value="1"]').checked=true;
                document.getElementById('f-energy').value='high';
                document.getElementById('f-due-day').value='1';
                document.getElementById('f-due-time').value='09:00';
                document.querySelector('#block-form button[type=submit]').click();""")
            wait_for("document.getElementById('status').textContent.startsWith('Saved')")
            evaluate("document.getElementById('solve').click()")
            wait_for("document.querySelector('.slack-tight')")
            evaluate("document.querySelector('.block:not(.flex-block)').click()")
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
        elif case == "download":
            submit_identity("draft_student", "register")
            server.stop()
            evaluate("""document.getElementById('add-flexible').click();
                document.getElementById('f-title').value='Offline draft';
                document.querySelector('input[name=f-day][value="0"]').checked=true;
                document.querySelector('#block-form button[type=submit]').click();""")
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
