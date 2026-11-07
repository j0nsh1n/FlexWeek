"""Opening the look editor in a window and driving it, for every test that works in it."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QWidget

from desktop.native.look import resolved_palette
from desktop.native.look_editor import LookEditor
from desktop.native.settings import SettingsPage
from desktop.native.window import NativeWindow


def pump(qapp: QApplication, times: int = 12) -> None:
    for _ in range(times):
        qapp.processEvents()


def palette_of(window: NativeWindow) -> dict:
    pack, dark, accent = window._look_inputs()
    return resolved_palette(pack, dark, window._look, accent)


def open_editor(qapp: QApplication, window: NativeWindow) -> tuple[SettingsPage, LookEditor]:
    window.resize(1280, 800)
    window._open_settings()
    page = window._settings
    pump(qapp)
    page.customise.click()
    pump(qapp)
    return page, page.editor


def type_colour(qapp: QApplication, editor: LookEditor, name: str, colour: str) -> None:
    field = editor.findChild(QWidget, f"lookColour-{name}")
    field.hex.setText(colour)
    field.hex.textEdited.emit(colour)
    pump(qapp)


def shown(editor: LookEditor, kind: type, name: str) -> list:
    return [child for child in editor.findChildren(kind, name) if child.isVisibleTo(editor)]


def name_look(qapp: QApplication, editor: LookEditor, name: str) -> None:
    editor.name.setText(name)
    editor.name.textEdited.emit(name)
    editor.name.editingFinished.emit()
    pump(qapp)
