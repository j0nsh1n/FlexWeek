"""Open the look-concepts mock-up in its own window.

Run from the repo root:

    ./.venv/bin/python docs/mockups/look-concepts/demo.py

This is a mock-up, not FlexWeek: it serves this folder on a free local port and shows
index.html in a Qt window. It reads and writes no FlexWeek data, and the browser profile is
off the record, so the sample week starts fresh each time the window opens.

    --check    load the page without showing a window, report what it found, and exit.
"""

from __future__ import annotations

import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication

HERE = Path(__file__).resolve().parent
CHECK_JS = "JSON.stringify({concepts: CONCEPTS.length, blocks: state.blocks.length, errors: window.__errors})"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


def serve() -> str:
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(HERE)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_address[1]}/"


def main() -> int:
    check = "--check" in sys.argv[1:]
    app = QApplication([arg for arg in sys.argv if arg != "--check"])
    app.setApplicationName("FlexWeek look concepts")
    view = QWebEngineView()
    view.setWindowTitle("FlexWeek look concepts: a mock-up, not the real app")
    view.resize(1500, 960)
    url = serve()

    if check:
        result: list[str] = []

        def report(value: object) -> None:
            result.append(str(value))
            app.quit()

        view.loadFinished.connect(
            lambda ok: QTimer.singleShot(1200, lambda: view.page().runJavaScript(CHECK_JS, report))
        )
        QTimer.singleShot(30000, app.quit)
        view.load(QUrl(url))
        app.exec()
        print(result[0] if result else "the page did not answer in time")
        return 0 if result and '"errors":[]' in result[0] else 1

    toggle = QShortcut(QKeySequence("F11"), view)
    toggle.activated.connect(lambda: view.showNormal() if view.isFullScreen() else view.showFullScreen())
    QShortcut(QKeySequence("Ctrl+Q"), view).activated.connect(view.close)
    QShortcut(QKeySequence("F5"), view).activated.connect(view.reload)
    QShortcut(QKeySequence("Alt+Left"), view).activated.connect(view.back)
    view.load(QUrl(url))
    view.show()
    view.setFocus()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
