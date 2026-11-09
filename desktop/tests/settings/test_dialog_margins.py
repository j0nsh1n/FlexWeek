"""Every dialog's content sits 24 px in from its edges, and a layout given margins of its own keeps them."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QWidget

from desktop.native.settings import AboutDialog
from desktop.native.widgets import DIALOG_MARGIN, use_app_style
from desktop.tests.window_support import qapp  # noqa: F401


def test_a_dialogs_content_sits_24_px_in_from_its_edges(qapp: QApplication, tmp_path: Path) -> None:  # noqa: F811
    """Qt's styles give a dialog about 11 px. The app's style gives every dialog 24, and a layout
    inside it, or one given margins of its own, keeps what it had. (A margin is a value the app's
    style sets, so it is checked here as a number, not on a picture.)"""
    use_app_style(qapp)
    host = QWidget()
    window_dialog = QDialog(host)
    margins = QVBoxLayout(window_dialog).contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (DIALOG_MARGIN,) * 4
    assert DIALOG_MARGIN == 24
    # A sheet draws its own card, which is padded the same 24 inside the room for its shadow.
    about = AboutDialog(host, None, str(tmp_path / "flexweek"))
    margins = about.card.layout().contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (DIALOG_MARGIN,) * 4
    plain = QDialog(host)
    outer = QVBoxLayout(plain)
    inner_host = QWidget()
    inner = QVBoxLayout(inner_host)
    outer.addWidget(inner_host)
    assert inner.contentsMargins().left() < DIALOG_MARGIN
    outer.setContentsMargins(0, 0, 0, 0)
    assert outer.contentsMargins().left() == 0
    host.deleteLater()
