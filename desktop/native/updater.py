"""Fetching a newer FlexWeek and putting it in place.

The deciding is in update.py, which is pure; this is the part that touches the network, the disk and
the running process, so it is written to fail safe at every step. A check that cannot reach GitHub
says nothing. A download that does not match its published checksum is deleted. An install directory
that cannot be written is reported rather than half-written. The app the student already has keeps
working in every one of those cases.

Nothing installs without the student pressing the button. The only thing that happens on its own is
the check, at most once a day, and that can be turned off.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import tarfile
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from desktop.native.update import (
    RELEASES_URL,
    Update,
    available,
    expected_digest,
    install_kind,
    verified,
)

USER_AGENT = b"FlexWeek-Updater"
DOWNLOAD_LIMIT = 400 * 1024 * 1024


class Updater(QObject):
    """One check, then one download, then one hand-off. Never two at once."""

    found = Signal(object)
    none_found = Signal()
    progress = Signal(int, int)
    failed = Signal(str)
    ready = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._manager = QNetworkAccessManager(self)
        self._busy = False
        self.kind = install_kind()

    @property
    def busy(self) -> bool:
        return self._busy

    def check(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._get(RELEASES_URL, self._on_release)

    def download(self, update: Update) -> None:
        if self._busy:
            return
        self._busy = True
        self._get(
            update["checksum_url"],
            lambda text: self._on_checksum(update, text),
        )

    def _get(self, url: str, then: object, binary: bool = False) -> None:
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"User-Agent", USER_AGENT)
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy,
        )
        reply = self._manager.get(request)
        if binary:
            reply.downloadProgress.connect(lambda got, total: self.progress.emit(got, max(total, 0)))
        reply.finished.connect(lambda: self._finish(reply, then, binary))

    def _finish(self, reply: QNetworkReply, then: object, binary: bool) -> None:
        data = bytes(reply.readAll().data())
        error = reply.error()
        reply.deleteLater()
        if error != QNetworkReply.NetworkError.NoError:
            # A check that cannot reach GitHub is not news. Say nothing and try again tomorrow.
            self._stop()
            return
        if len(data) > DOWNLOAD_LIMIT:
            self._give_up("That download was larger than any FlexWeek release.")
            return
        then(data if binary else data.decode("utf-8", "replace"))  # type: ignore[operator]

    def _stop(self) -> None:
        self._busy = False

    def _give_up(self, why: str) -> None:
        self._busy = False
        self.failed.emit(why)

    def _on_release(self, text: str) -> None:
        try:
            payload = json.loads(text)
        except ValueError:
            self._stop()
            return
        update = available(payload, self.kind)
        self._busy = False
        if update is None:
            self.none_found.emit()
            return
        self.found.emit(update)

    def _on_checksum(self, update: Update, text: str) -> None:
        digest = expected_digest(text, update["asset"])
        if digest is None:
            self._give_up("That release did not publish a checksum, so it was not downloaded.")
            return
        self._get(update["url"], lambda data: self._on_payload(update, digest, data), binary=True)

    def _on_payload(self, update: Update, digest: str, data: bytes) -> None:
        if not verified(data, digest):
            # Wrong bytes: a truncated download, a proxy, or something worse. Keep what works.
            self._give_up("The download did not match its checksum, so it was discarded.")
            return
        folder = Path(tempfile.mkdtemp(prefix="flexweek-update-"))
        target = folder / update["asset"]
        try:
            target.write_bytes(data)
            target.chmod(target.stat().st_mode | stat.S_IXUSR)
        except OSError:
            shutil.rmtree(folder, ignore_errors=True)
            self._give_up("The download could not be saved.")
            return
        self._busy = False
        self.ready.emit(str(target))


def bundle_root() -> Path:
    """The directory that would be replaced by a tarball update."""
    return Path(sys.executable).resolve().parent


def writable(path: Path) -> bool:
    return os.access(path, os.W_OK)


def apply_update(downloaded: str, kind: str | None = None) -> str | None:
    """Put the downloaded release in place. Returns None on success, or why it could not.

    The caller restarts the app afterwards; on Windows the installer does its own thing and the app
    simply quits.
    """
    how = install_kind() if kind is None else kind
    source = Path(downloaded)
    if how == "windows":
        from PySide6.QtCore import QProcess

        # Inno Setup upgrades an existing install in place; /SILENT keeps it to a progress window.
        started = QProcess.startDetached(str(source), ["/SILENT", "/NOCANCEL"])
        return None if started else "The installer would not start."
    if how == "appimage":
        current = os.environ.get("APPIMAGE")
        if not current:
            return "This copy does not know where its AppImage is."
        return _swap_file(source, Path(current))
    return _swap_tree(source)


def _swap_file(source: Path, target: Path) -> str | None:
    if not writable(target.parent):
        return f"{target.parent} cannot be written, so the update was not applied."
    try:
        beside = target.with_suffix(target.suffix + ".new")
        shutil.copy2(source, beside)
        beside.chmod(beside.stat().st_mode | stat.S_IXUSR)
        # Atomic on one filesystem: the file is either the old one or the new one, never half.
        os.replace(beside, target)
    except OSError as error:
        return f"The update could not be put in place: {error}"
    return None


def _swap_tree(source: Path) -> str | None:
    """Unpack a tarball over the running bundle by building the new one beside it and swapping.

    Writing into the live directory would leave a half-updated app if anything failed part way.
    """
    root = bundle_root()
    if not writable(root.parent):
        return f"{root.parent} cannot be written, so the update was not applied."
    staging = root.parent / (root.name + ".update")
    previous = root.parent / (root.name + ".old")
    try:
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True)
        with tarfile.open(source) as archive:
            _safe_extract(archive, staging)
        unpacked = next((child for child in staging.iterdir() if child.is_dir()), staging)
        shutil.rmtree(previous, ignore_errors=True)
        os.replace(root, previous)
        os.replace(unpacked, root)
    except (OSError, tarfile.TarError) as error:
        shutil.rmtree(staging, ignore_errors=True)
        if not root.exists() and previous.exists():
            os.replace(previous, root)
        return f"The update could not be put in place: {error}"
    shutil.rmtree(staging, ignore_errors=True)
    shutil.rmtree(previous, ignore_errors=True)
    return None


def _safe_extract(archive: tarfile.TarFile, destination: Path) -> None:
    """Refuse a member that would write outside the destination. A release is trusted, but a
    verified checksum proves the bytes came from GitHub, not that the archive is sane."""
    root = destination.resolve()
    for member in archive.getmembers():
        target = (root / member.name).resolve()
        if not target.is_relative_to(root):
            raise tarfile.TarError(f"{member.name} would be written outside the folder")
        if member.issym() or member.islnk():
            link = (target.parent / member.linkname).resolve()
            if not link.is_relative_to(root):
                raise tarfile.TarError(f"{member.name} links outside the folder")
    archive.extractall(destination, filter="tar")
