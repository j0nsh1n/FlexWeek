"""Runs the FlexWeek backend inside the desktop process. No Qt imports.

The desktop app is self-contained by default: it binds a loopback port, serves
the same FastAPI app the hosted deployment serves, and points the window at it.
Set FLEXWEEK_DESKTOP_ORIGIN (or FLEXWEEK_ORIGIN) to use a hosted server instead.

The port is chosen by binding a socket first, before the app is built. The
backend pins its CSRF origin check and TrustedHostMiddleware to one exact
origin, so the port has to be known before create_app is called; handing uvicorn
the already-bound socket also removes the race of picking a port and hoping it
is still free.
"""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import uvicorn

STARTUP_TIMEOUT_S = 30.0
SHUTDOWN_TIMEOUT_S = 5.0


class LocalServer:
    """The backend on a loopback port, in a background thread."""

    def __init__(self, database: Path) -> None:
        # Imported here, not at module scope: backend.app builds an app on import
        # and would raise on a bad FLEXWEEK_ORIGIN before main() can report it.
        from backend.app import create_app

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(("127.0.0.1", 0))
        self._socket.listen(128)
        self.port: int = self._socket.getsockname()[1]
        self.origin = f"http://127.0.0.1:{self.port}"

        config = uvicorn.Config(
            create_app(database=database, origin=self.origin),
            log_level="warning",
            # Explicit pure-Python loop and parser: uvloop/httptools are optional
            # native extras that need not survive being frozen into a bundle.
            loop="asyncio",
            http="h11",
            # FlexWeek serves no WebSockets, and the desktop build leaves the
            # websockets package out.
            ws="none",
        )
        self._server = uvicorn.Server(config)
        self._thread: threading.Thread | None = None

    def start(self, timeout: float = STARTUP_TIMEOUT_S) -> str:
        """Serve, block until the port is accepting, and return the origin."""
        self._thread = threading.Thread(target=self._serve, name="flexweek-server", daemon=True)
        self._thread.start()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._server.started:
                return self.origin
            if not self._thread.is_alive():
                raise RuntimeError("FlexWeek server thread stopped before it began serving")
            time.sleep(0.02)
        self.stop()
        raise TimeoutError(f"FlexWeek server did not start within {timeout:g}s")

    def _serve(self) -> None:
        self._server.run(sockets=[self._socket])

    @property
    def is_running(self) -> bool:
        """True while the serving thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    def stop(self, timeout: float = SHUTDOWN_TIMEOUT_S) -> None:
        self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout)
        # uvicorn closes the socket on a clean exit; closing twice is harmless
        # and this covers the path where startup timed out.
        self._socket.close()
