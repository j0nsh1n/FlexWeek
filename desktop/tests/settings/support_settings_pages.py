"""What the tests of the Settings page (the Widgets styles page the gear opens) share: opening it, the
sections' numbers, finding a form row's label and a look card by name."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QFormLayout, QLabel, QWidget

from desktop.native.layouts.registry import sanitize_layout
from desktop.native.look import resolved_palette
from desktop.native.settings import SettingsPage
from desktop.native.widgets import ChoiceCard
from desktop.native.window import NativeWindow

APPEARANCE, PLANNING, FOCUS, ALERTS, COMPUTER = range(5)


def prefs(
    window: NativeWindow, layout: dict | None = None, size: tuple[int, int] | None = None
) -> SettingsPage:
    """Settings as the gear opens it, in place of the week."""
    if layout is not None:
        window._layout = sanitize_layout(layout)
    if size is not None:
        window.resize(*size)
    window._open_settings()
    dialog = window._settings
    assert dialog is not None and window._stack.currentWidget() is dialog
    for _ in range(5):
        QApplication.processEvents()
    return dialog


def show_section(dialog: SettingsPage, row: int) -> QWidget:
    dialog.nav.setCurrentRow(row)
    for _ in range(5):
        QApplication.processEvents()
    return dialog.stack.widget(row).widget()


def page(dialog: SettingsPage, row: int) -> QWidget:
    return dialog.stack.widget(row).widget()


def label_for(widget: QWidget) -> str:
    # A number is stepped by - and + around it, and the three are the form's field together.
    if widget.parentWidget().objectName() == "stepper":
        widget = widget.parentWidget()
    form = widget.parentWidget().layout()
    assert isinstance(form, QFormLayout)
    label = form.labelForField(widget)
    return label.text() if isinstance(label, QLabel) else ""


def tile(dialog: SettingsPage, name: str) -> ChoiceCard:
    # The worn card's accessible name is "<name>, selected".
    for card in dialog.look.more.cards:
        look = getattr(card, "_look_name", None)
        if look == name:
            return card
        shown = card.accessibleName()
        if shown == name or shown == f"{name}, selected":
            return card
    raise LookupError(name)


def palette_of(window: NativeWindow) -> dict:
    pack, dark, accent = window._look_inputs()
    return resolved_palette(pack, dark, window._look, accent)


def visible_words(card: QWidget) -> list[str]:
    return [label.text() for label in card.findChildren(QLabel) if label.isVisibleTo(card)]
