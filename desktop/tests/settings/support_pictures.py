"""What the settings pictures do to a light window before it is photographed. Nothing here asserts: a
picture is judged by the reviewer from the checks its screen lists."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from desktop.native.look import resolved_palette, sanitize_look
from desktop.native.menus import Menu, menu_colours
from desktop.native.settings import SettingsPage
from desktop.native.widgets import Segment, Segmented, SegmentTrack, Switch, add_heading
from desktop.native.window import NativeWindow
from desktop.tests.settings.support_tokens import LOOKS
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import still


def pump(done: Callable[[], bool]) -> None:
    """Wait for `done`, and go on when it does not come: a picture of a screen that did not finish is
    still a picture the reviewer can judge."""
    try:
        wait_until(None, done, timeout=5.0)
    except AssertionError:
        return


def wear(window: NativeWindow, name: str) -> None:
    """Dress the window in one of the ten looks of support_tokens.LOOKS, as a student's choice does."""
    pack, _dark, chosen = LOOKS[name]
    look = sanitize_look(chosen or {"preset": "default", "knobs": {}})
    window._look = look
    window.session.look = look
    if window.session.preferences is not None:
        window.session.preferences = {**window.session.preferences, "theme_pack": pack}
    window._apply_appearance()
    still(window)


def palette_of(window: NativeWindow) -> dict:
    pack, system_dark, accent = window._look_inputs()
    return resolved_palette(pack, system_dark, window._worn_look(), accent)


def settings_at(window: NativeWindow, row: int = 0, size: tuple[int, int] | None = None) -> SettingsPage:
    """Settings open on a section, at a window size, with the style preview drawn when the section has one."""
    if size is not None:
        window.resize(*size)
    window._open_settings_at(row)
    page = window._settings
    assert page is not None, "Settings did not open"
    if row == 0:
        preview = page.style_preview
        pump(lambda: preview.isVisible() and not preview.stage.pictures[0].source.isNull())
    still(window)
    return page


def wear_large_text(page: SettingsPage) -> None:
    text = page.knobs["text"]
    text.setCurrentIndex(text.findData("large"))
    pump(lambda: False)


def controls_sample(window: NativeWindow) -> QWidget:
    """Every kind of control the app styles by hand, in the window's current look."""
    sample = QFrame(window)
    sample.setObjectName("controlsSample")
    sample.setAutoFillBackground(True)
    column = QVBoxLayout(sample)
    box = QCheckBox("Play a sound")
    ticked = QCheckBox("Remind me")
    ticked.setChecked(True)
    radio = QRadioButton("I'll place it")
    spin = QSpinBox()
    spin.setValue(25)
    combo = QComboBox()
    combo.addItems(["Calendar · Today's app", "Agenda · Timeline", "Dashboard · Bento"])
    combo.setCurrentIndex(2)
    switch = Switch("Remind before starting")
    choice = Segmented((("Light", "light"), ("Dark", "dark"), ("System", "system")), "lookChoice")
    choice.setCurrentIndex(1)
    track = SegmentTrack()
    track.setObjectName("segments")
    QHBoxLayout(track)
    for name, words in (("viewDay", "Day"), ("viewWeek", "Week"), ("viewMonth", "Month")):
        button = Segment(words)
        button.setObjectName(name)
        button.setCheckable(True)
        button.setChecked(name == "viewWeek")
        track.add(button)
    field = QLineEdit()
    field.setPlaceholderText("e.g. History essay")
    notes = QPlainTextEdit()
    notes.setPlaceholderText("e.g. History essay")
    notes.setFixedHeight(60)
    time = QTimeEdit()
    buttons = QHBoxLayout()
    kinds = {"Done": {}, "Check for updates": {"outlined": True, "outline": True}, "Tonal": {"tonal": True}}
    for words, properties in kinds.items():
        pressed = QPushButton(words)
        for key, value in properties.items():
            pressed.setProperty(key, value)
        buttons.addWidget(pressed)
    delete = QPushButton("Delete")
    delete.setProperty("outlined", True)
    delete.setProperty("danger", True)
    buttons.addWidget(delete)
    off = QPushButton("Plan my homework")
    off.setEnabled(False)
    buttons.addWidget(off)
    for piece in (box, ticked, radio, spin, combo, switch, choice, track, field, notes, time):
        column.addWidget(piece)
    column.addLayout(buttons)
    sample.setGeometry(20, 20, 560, 560)
    sample.raise_()
    sample.show()
    still(sample)
    return sample


def dropdown_list(window: NativeWindow) -> QWidget:
    """A dropdown with its list open and the third choice chosen."""
    sample = QFrame(window)
    sample.setObjectName("dropdownSample")
    column = QVBoxLayout(sample)
    combo = QComboBox()
    combo.addItems(["Calendar · Today's app", "Agenda · Timeline", "Dashboard · Bento"])
    combo.setCurrentIndex(2)
    column.addWidget(combo)
    sample.setGeometry(20, 20, 320, 80)
    sample.raise_()
    sample.show()
    combo.showPopup()
    pump(lambda: combo.view().isVisible())
    return combo.view()


def toast_with_undo(window: NativeWindow) -> QWidget:
    window.toast.show_message("Homework deleted", "Undo", lambda: None)
    still(window)
    return window.toast


def open_menu(window: NativeWindow) -> Menu:
    """A menu with a heading, rows (the second under the pointer) and a submenu, opened at (300, 200)."""
    menu = Menu(window)
    menu.set_colours(menu_colours(palette_of(window), lifted=True))
    add_heading(menu, "Adding")
    menu.add("Add homework", "plus")
    menu.add("Open", "pencil", keys="Enter")
    menu.add("Delete", "trash", danger=True)
    menu.add_menu("Undo, copy and save", "undo-2")
    menu.popup(QPoint(300, 200))
    pump(lambda: menu.isVisible())
    menu.setActiveAction(menu.actions()[2])
    return menu
