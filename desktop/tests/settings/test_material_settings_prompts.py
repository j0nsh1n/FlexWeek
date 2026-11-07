"""Material 3 Settings prompts (save, import, export, keep-the-dials): while one is open it owns the
keys and the pointer. Shell shortcuts do nothing, Tab stays inside the prompt and wraps, and the top
bar's Undo, Redo and More are idle until it closes."""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.native.window import NativeWindow
from desktop.tests.light_app import window  # noqa: F401
from desktop.tests.settings.support_material_settings import (
    _bridge,
    _click,
    _named,
    _open_settings,
    _panel,
    _pump,
    _qml,
    school_week_with_an_essay,
)
from desktop.tests.waiting import wait_until
from desktop.tests.window_support import qapp  # noqa: F401

# ruff: noqa: F811


def _lineage(item: QObject | None) -> list[str]:
    out: list[str] = []
    while item is not None:
        out.append(str(item.objectName() or type(item).__name__))
        item = item.parentItem() if hasattr(item, "parentItem") else None
    return out


def _assert_shortcuts_blocked(qapp: QApplication, window: NativeWindow, root: QObject) -> None:
    bridge = _bridge(window)
    quick = window._material_page._quick
    before = bridge.property("screen")
    for key in (
        Qt.Key.Key_1,
        Qt.Key.Key_2,
        Qt.Key.Key_3,
        Qt.Key.Key_4,
        Qt.Key.Key_5,
        Qt.Key.Key_Z,
        Qt.Key.Key_F,
        Qt.Key.Key_P,
    ):
        QTest.keyClick(quick, key)
        _pump(qapp)
        assert bridge.property("screen") == before
        assert not window._material_page.bridge.focus.open
    for _ in range(8):
        QTest.keyClick(quick, Qt.Key.Key_Tab)
        _pump(qapp, 3)
        chain = _lineage(quick.quickWindow().activeFocusItem())
        assert "navWeek" not in chain
        assert "materialFab" not in chain
        names = (
            "savePrompt",
            "importPrompt",
            "exportPrompt",
            "presetPrompt",
            "promptCard",
            "promptField",
        )
        assert any(name in chain for name in names)


def _week_marks(window: NativeWindow) -> tuple:
    return tuple(
        (
            str(block.get("id")),
            block.get("start"),
            tuple(block.get("days") or []),
            bool(block.get("completed")),
        )
        for block in window.session.blocks
    )


def _tools(root: QObject) -> QObject:
    return _qml(root, "materialUndo").parentItem()


def _prompt_child(prompt: QObject, *names: str) -> QObject | None:
    for name in names:
        for item in _named(prompt, name):
            return item
    return None


def _assert_prompt_owns_keys(
    qapp: QApplication, window: NativeWindow, root: QObject, prompt: QObject
) -> None:
    prompt.forceActiveFocus()
    _pump(qapp)
    _assert_shortcuts_blocked(qapp, window, root)
    cancel = _prompt_child(prompt, "prompt_cancel", "prompt_close")
    if cancel is not None:
        cancel.forceActiveFocus()
        _pump(qapp)
        _assert_shortcuts_blocked(qapp, window, root)
        QTest.keyClick(window._material_page._quick, Qt.Key.Key_Backtab)
        _pump(qapp, 3)
        chain = _lineage(window._material_page._quick.quickWindow().activeFocusItem())
        assert any(
            name in chain
            for name in (
                "savePrompt",
                "importPrompt",
                "exportPrompt",
                "presetPrompt",
                "promptCard",
                "promptField",
                "prompt_cancel",
                "prompt_close",
                "prompt_save",
                "prompt_import",
                "prompt_copy",
                "prompt_keep",
                "prompt_discard",
            )
        )


def _assert_top_bar_idle(qapp: QApplication, window: NativeWindow, root: QObject) -> None:
    bridge = _bridge(window)
    marks = _week_marks(window)
    undoable = window.session.can_undo()
    redoable = window.session.can_redo()
    tools = _tools(root)
    undo = _qml(root, "materialUndo")
    redo = _qml(root, "materialRedo")
    more = _qml(root, "materialMore")
    assert tools.property("enabled") is False
    assert undo.property("enabled") is False
    assert redo.property("enabled") is False
    assert more.property("enabled") is False
    _click(qapp, window, undo)
    assert _week_marks(window) == marks
    assert window.session.can_undo() is undoable
    _click(qapp, window, redo)
    assert _week_marks(window) == marks
    assert window.session.can_redo() is redoable
    _click(qapp, window, more)
    assert bridge.sheets.moreOpen is False
    assert bridge.property("screen") == "settings"


def test_settings_prompts_block_the_top_bar_pointer(
    qapp: QApplication, window: NativeWindow
) -> None:
    """Undo, Redo and More must not act while a Settings prompt is open."""
    school_week_with_an_essay(qapp, window)
    root = _open_settings(qapp, window)
    panel = _panel(window)
    bridge = _bridge(window)
    window.session.complete_homework("essay")
    window.session.save()
    wait_until(qapp, lambda: not window.session.busy and window.session.can_undo())
    marks_before = _week_marks(window)
    assert window.session.can_undo()
    panel.openAdvanced()
    _pump(qapp)
    for open_prompt, name, has_field in (
        (panel.beginSave, "savePrompt", True),
        (panel.beginImport, "importPrompt", True),
        (panel.beginExport, "exportPrompt", False),
    ):
        open_prompt()
        _pump(qapp)
        prompt = _named(root, name)[0]
        assert prompt.property("open")
        _assert_top_bar_idle(qapp, window, root)
        _assert_prompt_owns_keys(qapp, window, root, prompt)
        if has_field:
            field = _prompt_child(prompt, "fieldInput")
            assert field is not None
            field.forceActiveFocus()
            _pump(qapp)
            before = str(field.property("text") or "")
            QTest.keyClick(window._material_page._quick, Qt.Key.Key_2)
            _pump(qapp)
            assert str(field.property("text") or "") == before + "2"
            assert bridge.property("screen") == "settings"
        cancel = _prompt_child(prompt, "prompt_cancel", "prompt_close")
        assert cancel is not None
        assert cancel.property("enabled") is True
        _click(qapp, window, cancel)
        _pump(qapp)
        assert prompt.property("open") is False
    panel.setCorner(4)
    panel.done()
    _pump(qapp)
    panel.setPreset("Sea")
    _pump(qapp)
    prompt = _named(root, "presetPrompt")[0]
    assert prompt.property("open")
    _assert_top_bar_idle(qapp, window, root)
    _assert_prompt_owns_keys(qapp, window, root, prompt)
    keep = _named(root, "prompt_keep")[0]
    assert keep.property("enabled") is True
    panel.answerPreset("cancel")
    _pump(qapp)
    assert panel.property("promptOpen") is False
    tools = _tools(root)
    undo = _qml(root, "materialUndo")
    more = _qml(root, "materialMore")
    assert tools.property("enabled") is True
    assert undo.property("enabled") is True
    assert more.property("enabled") is True
    _click(qapp, window, more)
    assert bridge.sheets.moreOpen is True
    bridge.sheets.closeMore()
    _pump(qapp)
    _click(qapp, window, undo)
    wait_until(qapp, lambda: not window.session.busy)
    assert _week_marks(window) != marks_before
    root.forceActiveFocus()
    _pump(qapp)
    QTest.keyClick(window._material_page._quick, Qt.Key.Key_2)
    _pump(qapp)
    assert bridge.property("screen") == "week"


def test_settings_prompts_block_shell_shortcuts_and_keep_tab(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window)
    panel = _panel(window)
    bridge = _bridge(window)
    quick = window._material_page._quick
    panel.openAdvanced()
    _pump(qapp)
    panel.beginSave()
    _pump(qapp)
    prompt = _named(root, "savePrompt")[0]
    assert prompt.property("open")
    assert panel.property("promptOpen") is True
    prompt.forceActiveFocus()
    _pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_2)
    _pump(qapp)
    assert bridge.property("screen") == "settings"
    assert prompt.property("open")
    _assert_shortcuts_blocked(qapp, window, root)
    field = _named(root, "promptField")[0]
    field.forceActiveFocus()
    _pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_2)
    _pump(qapp)
    assert bridge.property("screen") == "settings"
    panel.dismissPrompt()
    _pump(qapp)
    panel.beginImport()
    _pump(qapp)
    assert _named(root, "importPrompt")[0].property("open")
    _named(root, "importPrompt")[0].forceActiveFocus()
    QTest.keyClick(quick, Qt.Key.Key_3)
    _pump(qapp)
    assert bridge.property("screen") == "settings"
    panel.dismissPrompt()
    panel.beginExport()
    _pump(qapp)
    assert _named(root, "exportPrompt")[0].property("open")
    _named(root, "exportPrompt")[0].forceActiveFocus()
    QTest.keyClick(quick, Qt.Key.Key_4)
    _pump(qapp)
    assert bridge.property("screen") == "settings"
    panel.dismissPrompt()
    panel.setCorner(4)
    panel.done()
    _pump(qapp)
    panel.setPreset("Sea")
    _pump(qapp)
    assert panel.property("state")["askPreset"] is True
    _named(root, "presetPrompt")[0].forceActiveFocus()
    QTest.keyClick(quick, Qt.Key.Key_2)
    _pump(qapp)
    assert bridge.property("screen") == "settings"
    panel.answerPreset("cancel")
    _pump(qapp)
    assert panel.property("promptOpen") is False
    root.forceActiveFocus()
    _pump(qapp)
    QTest.keyClick(quick, Qt.Key.Key_2)
    _pump(qapp)
    assert bridge.property("screen") == "week"


PROMPT_OWNERS = (
    "savePrompt",
    "promptCard",
    "promptField",
    "prompt_cancel",
    "prompt_save",
    "fieldInput",
)
PROMPT_GENERIC = {"", "fieldInput", "shape", "label", "promptCard", "savePrompt", "materialShell"}


def _prompt_semantic(chain: list[str]) -> str:
    for name in chain:
        if name.startswith("QQuick") or name in PROMPT_GENERIC:
            continue
        return name
    return chain[0] if chain else "(none)"


def test_settings_save_prompt_tab_advances_from_the_field_and_wraps(
    qapp: QApplication, window: NativeWindow
) -> None:
    root = _open_settings(qapp, window)
    panel = _panel(window)
    quick = window._material_page._quick
    panel.openAdvanced()
    _pump(qapp)
    panel.beginSave()
    _pump(qapp)
    prompt = _named(root, "savePrompt")[0]
    assert prompt.property("open") is True
    start_chain = _lineage(quick.quickWindow().activeFocusItem())
    start = _prompt_semantic(start_chain)
    assert start == "promptField", f"initial focus was {start}: {start_chain}"
    forward: list[str] = []
    for _ in range(8):
        QTest.keyClick(quick, Qt.Key.Key_Tab)
        _pump(qapp, 3)
        chain = _lineage(quick.quickWindow().activeFocusItem())
        name = _prompt_semantic(chain)
        assert any(owner in chain for owner in PROMPT_OWNERS), f"Tab left the prompt: {chain}"
        assert "navWeek" not in chain and "materialFab" not in chain
        if not forward:
            assert name != start, f"Tab did not leave {start}: {chain}"
        if name == start:
            break
        forward.append(name)
    else:
        raise AssertionError(f"Tab never wrapped back to {start}; visited {forward}")
    assert len(forward) == len(set(forward)), f"Tab repeated a control: {forward}"
    assert len(forward) >= 2, f"Tab stayed on one control: {forward}"
    for name in ("prompt_cancel", "prompt_save"):
        assert name in forward, f"{name} missing from {forward}"
    backward: list[str] = []
    for _ in range(8):
        QTest.keyClick(quick, Qt.Key.Key_Backtab)
        _pump(qapp, 3)
        chain = _lineage(quick.quickWindow().activeFocusItem())
        name = _prompt_semantic(chain)
        assert any(owner in chain for owner in PROMPT_OWNERS), f"Backtab left the prompt: {chain}"
        if not backward:
            assert name != start, f"Backtab did not leave {start}: {chain}"
        if name == start:
            break
        backward.append(name)
    else:
        raise AssertionError(f"Backtab never wrapped back to {start}; visited {backward}")
    assert backward == list(reversed(forward)), f"Backtab {backward} was not the reverse of {forward}"
    field = _prompt_child(prompt, "fieldInput")
    assert field is not None
    field.forceActiveFocus()
    _pump(qapp)
    before = str(field.property("text") or "")
    QTest.keyClick(quick, Qt.Key.Key_A)
    _pump(qapp)
    assert str(field.property("text") or "") == before + "a"
