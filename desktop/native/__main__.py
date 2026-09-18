"""Launch FlexWeek as Qt widgets with no browser engine."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QIcon
from PySide6.QtNetwork import QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox

import backend
from desktop.native.window import NativeWindow
from desktop.origin import configured_origin
from desktop.server import LocalServer

INSTANCE_WAIT_MS = 500


def app_icon_path() -> Path:
    return Path(backend.__file__).resolve().parents[1] / "frontend" / "logo.png"


def instance_name(root: str) -> str:
    return "flexweek-" + hashlib.sha256(root.encode()).hexdigest()[:16]


def show_running_instance(name: str) -> bool:
    socket = QLocalSocket()
    socket.connectToServer(name)
    if not socket.waitForConnected(INSTANCE_WAIT_MS):
        return False
    socket.write(b"show")
    socket.waitForBytesWritten(INSTANCE_WAIT_MS)
    socket.disconnectFromServer()
    return True


def profile_root() -> str:
    return QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)


def parse_database(argv: list[str]) -> tuple[list[str], Path | None]:
    filtered = [argv[0]]
    database: Path | None = None
    index = 1
    while index < len(argv):
        if argv[index] == "--database" and index + 1 < len(argv):
            database = Path(argv[index + 1])
            index += 2
            continue
        filtered.append(argv[index])
        index += 1
    return filtered, database


def main(argv: list[str] | None = None) -> int:
    arguments, database_arg = parse_database(list(argv if argv is not None else sys.argv))
    app = QApplication(arguments)
    app.setApplicationName("FlexWeek")
    app.setDesktopFileName("flexweek")

    try:
        origin = configured_origin()
    except ValueError as error:
        QMessageBox.critical(None, "FlexWeek configuration", str(error))
        return 2

    root = profile_root()
    instance = instance_name(str(database_arg) if database_arg is not None else root)
    if show_running_instance(instance):
        return 0

    hosted = origin is not None and database_arg is None
    server: LocalServer | None = None
    if not hosted:
        database = database_arg if database_arg is not None else Path(root) / "flexweek.db"
        try:
            database.parent.mkdir(parents=True, exist_ok=True)
            server = LocalServer(database, serve_frontend=False)
            origin = server.start()
        except (OSError, RuntimeError, TimeoutError) as error:
            QMessageBox.critical(None, "FlexWeek", f"Could not start FlexWeek: {error}")
            return 3
        app.aboutToQuit.connect(server.stop)
    assert origin is not None

    window = NativeWindow(origin, icon=QIcon(str(app_icon_path())))
    window.listen_for_instances(instance)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
