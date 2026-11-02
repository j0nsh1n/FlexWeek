import QtQuick
import components 1.0

// Everything that sits over the screens: the open sheet, the question on top of it, the More
// menu, and the notice a finished sheet leaves. Esc closes; focus goes back to where it was.
Item {
    id: root
    objectName: "sheetHost"
    property var bridge
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool phone: false
    // The bridge is cleared while the page is torn down.
    readonly property var sheets: bridge ? bridge.sheets : null
    readonly property string kind: sheets ? sheets.kind : ""
    readonly property bool asking: sheets ? sheets.ask.id !== undefined : false
    readonly property bool menu: sheets ? sheets.moreOpen : false
    readonly property bool active: sheets ? sheets.active : false
    property Item before: null
    readonly property Item focused: Window.activeFocusItem
    signal restoreFocus(Item item)

    anchors.fill: parent
    // Clicks and keys go to the sheet while it is open, not to the screen behind it.
    enabled: true
    visible: active || notice.visible

    function inside(item) {
        while (item) {
            if (item === root)
                return true
            item = item.parent
        }
        return false
    }

    function remember() {
        var held = focused
        if (held && !inside(held))
            before = held
    }

    onFocusedChanged: {
        if (!active && focused && !inside(focused))
            before = focused
    }

    function returnFocus() {
        var held = before
        before = null
        Qt.callLater(function () {
            if (held && held.visible) {
                held.forceActiveFocus()
            } else {
                restoreFocus(null)
            }
        })
    }

    onActiveChanged: {
        if (active)
            Qt.callLater(function () {
                if (menu)
                    more.focusFirst()
                else if (loader.item)
                    loader.item.focusFirst()
            })
        else
            returnFocus()
    }
    onAskingChanged: {
        if (asking)
            Qt.callLater(function () { if (prompt.item) prompt.item.focusFirst() })
        else if (active && loader.item)
            Qt.callLater(function () { if (loader.item) loader.item.focusFirst() })
    }
    onKindChanged: {
        if (kind !== "" && loader.item)
            Qt.callLater(function () { if (loader.item) loader.item.focusFirst() })
    }
    onMenuChanged: if (menu) remember()

    Connections {
        target: root.sheets
        function onChanged() {
            if (root.sheets.kind !== "" && root.before === null)
                root.remember()
        }
    }

    Loader {
        id: loader
        anchors.fill: parent
        active: root.kind !== ""
        sourceComponent: {
            switch (root.kind) {
            case "homework": return homework
            case "block": return block
            case "late": return late
            case "unfinished": return unfinished
            case "weekList": return weekList
            case "routines": return routines
            }
            return null
        }
    }
    Component { id: homework; HomeworkSheet { sheets: root.sheets; theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; phone: root.phone } }
    Component { id: block; BlockSheet { sheets: root.sheets; theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; phone: root.phone } }
    Component { id: late; LateSheet { sheets: root.sheets; theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; phone: root.phone } }
    Component { id: unfinished; UnfinishedSheet { sheets: root.sheets; theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; phone: root.phone } }
    Component { id: weekList; WeekListSheet { sheets: root.sheets; theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; phone: root.phone } }
    Component { id: routines; RoutinesSheet { sheets: root.sheets; theme: root.theme; density: root.density; reduceMotion: root.reduceMotion; highContrast: root.highContrast; phone: root.phone } }

    Loader {
        id: prompt
        anchors.fill: parent
        z: 2
        active: root.asking
        sourceComponent: askDialog
    }
    Component {
        id: askDialog
        PromptDialog {
            sheets: root.sheets
            theme: root.theme
            density: root.density
            reduceMotion: root.reduceMotion
            highContrast: root.highContrast
            phone: root.phone
        }
    }

    MoreMenu {
        id: more
        objectName: "materialMore"
        visible: root.menu
        z: 1
        sheets: root.sheets
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        phone: root.phone
        onCloseRequested: root.sheets.closeMore()
    }

    Shortcut {
        sequence: "Escape"
        context: Qt.WindowShortcut
        enabled: root.active
        onActivated: root.menu ? root.sheets.closeMore() : root.sheets.closeSheet()
    }

    Snackbar {
        id: notice
        objectName: "sheetNotice"
        visible: root.sheets !== null && root.sheets.notice !== ""
        z: 3
        message: root.sheets ? root.sheets.notice : ""
        actionText: root.sheets && root.sheets.noticeUndo ? "UNDO" : "OK"
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: root.phone ? 96 : 24
        onActionClicked: root.sheets.noticeUndo ? root.sheets.undoNotice() : root.sheets.dismissNotice()
    }
}
