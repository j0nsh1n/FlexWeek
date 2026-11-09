"""The recovery codes page after creating an account: eight codes, copied or saved by a button, kept
in no widget once the week is open, and built again when new codes are made."""

# ruff: noqa: F811  (pytest fixtures imported by name)

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from desktop.native import window as window_module
from desktop.native.window import NativeWindow
from desktop.tests.account.support import LightLaunches, light_launches, on_recovery_page, page  # noqa: F401
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

CODE_SHAPE = re.compile(r"[0-9a-f]{4}(?:-[0-9a-f]{4}){3}")


def codes(window: NativeWindow) -> list[str]:
    return window.recovery_list.text().splitlines()


@pytest.fixture()
def recovering(qapp: QApplication, light_launches: LightLaunches) -> Iterator[NativeWindow]:
    with light_launches.launched() as window:
        on_recovery_page(qapp, window)
        yield window


def test_the_page_shows_eight_codes_one_per_line(recovering: NativeWindow) -> None:
    assert len(codes(recovering)) == 8
    assert all(CODE_SHAPE.fullmatch(code) for code in codes(recovering))


def test_both_cards_name_flexweek_beside_its_icon(recovering: NativeWindow) -> None:
    for name in ("authPage", "recoveryPage"):
        card = next(w for w in recovering._stack.findChildren(QWidget) if w.objectName() == name)
        icon = card.findChild(QLabel, "authLogo")
        brand = card.findChild(QLabel, "authBrand")
        assert brand.text() == "FlexWeek"
        assert icon is not None and not icon.pixmap().isNull(), name
        assert icon.parentWidget() is brand.parentWidget()


def test_copy_puts_every_code_on_the_clipboard_and_says_so_for_a_moment(
    qapp: QApplication, recovering: NativeWindow
) -> None:
    QApplication.clipboard().clear()
    recovering.recovery_copy.click()
    assert QApplication.clipboard().text().splitlines() == codes(recovering)
    assert recovering.recovery_copy.text() == "Copied"
    wait_until(qapp, lambda: recovering.recovery_copy.text() == "Copy", timeout=4.0)


def test_save_writes_the_codes_one_per_line_where_the_student_chose(
    qapp: QApplication, recovering: NativeWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chosen = tmp_path / "my-codes.txt"
    monkeypatch.setattr(recovering, "_choose_recovery_file", lambda: str(chosen))
    assert recovering.recovery_save.text() == "Save…"
    recovering.recovery_save.click()
    assert chosen.read_text().splitlines() == codes(recovering)
    assert recovering.recovery_save.text() == "Saved"
    wait_until(qapp, lambda: recovering.recovery_save.text() == "Save…", timeout=4.0)


def test_save_cancelled_writes_nothing_and_a_folder_it_cannot_write_says_so(
    recovering: NativeWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(recovering, "_choose_recovery_file", lambda: "")
    recovering.recovery_save.click()
    assert list(tmp_path.glob("*.txt")) == []
    assert recovering.recovery_save.text() == "Save…"
    monkeypatch.setattr(recovering, "_choose_recovery_file", lambda: str(tmp_path / "missing" / "codes.txt"))
    recovering.recovery_save.click()
    assert recovering.recovery_status.isVisibleTo(recovering)
    assert recovering.recovery_status.text() == "FlexWeek could not save the codes there. Try another folder."
    assert recovering.recovery_save.text() == "Save…"


def test_the_default_file_name_is_offered_to_the_dialog(
    recovering: NativeWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []

    def answer(_parent: object, _caption: str, name: str, _kinds: str) -> tuple[str, str]:
        asked.append(name)
        return "", ""

    monkeypatch.setattr(window_module.QFileDialog, "getSaveFileName", staticmethod(answer))
    # Save… opens a sheet first; the file dialog is what the sheet's answer opens.
    recovering._pick_recovery_file()
    assert [Path(name).name for name in asked] == ["flexweek-recovery-codes.txt"]


def words_held(widget: QWidget) -> list[str]:
    """Every text a widget gives out, to the eye or to a screen reader."""
    held = [widget.accessibleName(), widget.accessibleDescription(), widget.toolTip()]
    for reader in ("text", "toPlainText"):
        read = getattr(widget, reader, None)
        # A few of the app's own widgets keep a child called `text`, which is not a reader.
        if callable(read) and isinstance(said := read(), str):
            held.append(said)
    return held


def test_no_widget_holds_a_recovery_code_once_the_week_is_open(
    qapp: QApplication, recovering: NativeWindow
) -> None:
    """Eight codes stayed in a hidden label, in memory and in the accessibility tree."""
    saved = codes(recovering)
    assert len(saved) == 8 and all(CODE_SHAPE.fullmatch(code) for code in saved)
    recovering.recovery_ack.setChecked(True)
    recovering.recovery_continue.click()
    wait_until(qapp, lambda: page(recovering) != "recoveryPage" and not recovering.session.busy)
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()
    for widget in QApplication.allWidgets():
        for text in words_held(widget):
            assert not CODE_SHAPE.search(text), (widget.objectName(), text)
    assert recovering.findChild(QWidget, "recoveryPage") is None


def test_the_recovery_page_comes_back_when_new_codes_are_made(
    qapp: QApplication, recovering: NativeWindow
) -> None:
    """The page is deleted after the first save, so replacing the codes has to build it again."""
    recovering.recovery_ack.setChecked(True)
    recovering.recovery_continue.click()
    wait_until(qapp, lambda: page(recovering) != "recoveryPage" and not recovering.session.busy)
    recovering.session.recovery_codes.emit(["aaaa-bbbb-cccc-dddd"] * 8)
    assert page(recovering) == "recoveryPage"
    assert codes(recovering) == ["aaaa-bbbb-cccc-dddd"] * 8
    recovering.recovery_copy.click()
    assert QApplication.clipboard().text().splitlines() == codes(recovering)
