import QtQuick
import components 1.0

// The More menu: Planning, Edit, Help and info, Account. It hangs under the top bar's More button.
FocusScope {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool phone: false
    property var sheets
    readonly property var entries: sheets ? sheets.moreEntries : []
    property int cursor: -1
    signal closeRequested()
    anchors.fill: parent
    M3Palette { id: pal; theme: root.theme }

    function usable(i) { return entries[i] && entries[i].heading === "" && entries[i].enabled }
    function step(by) {
        if (entries.length === 0)
            return
        var at = cursor
        for (var n = 0; n < entries.length; n++) {
            at = (at + by + entries.length) % entries.length
            if (usable(at)) {
                cursor = at
                return
            }
        }
    }
    function focusFirst() {
        cursor = -1
        step(1)
        root.forceActiveFocus()
    }

    Rectangle {
        anchors.fill: parent
        color: "transparent"
        TapHandler { onTapped: root.closeRequested() }
    }
    Rectangle {
        id: card
        objectName: "materialMoreMenu"
        width: 280
        height: column.height + 16
        radius: 4
        x: root.width - width - 8
        y: 56
        color: pal.surfaceContainer
        border.width: root.highContrast ? 1.5 : 0
        border.color: pal.outlineVariant
        // A soft shadow, drawn as a darker rectangle under the card.
        Rectangle {
            z: -1
            anchors.fill: parent
            anchors.topMargin: 4
            radius: 4
            color: "#4d000000"
        }
        Column {
            id: column
            y: 8
            width: parent.width
            Repeater {
                model: root.entries
                delegate: Item {
                    id: row
                    objectName: modelData.heading !== "" ? "moreHeading" : "more_" + modelData.id
                    readonly property bool head: modelData.heading !== ""
                    readonly property bool hot: root.cursor === index
                    width: column.width
                    height: head ? 36 : 44
                    Accessible.role: head ? Accessible.StaticText : Accessible.MenuItem
                    Accessible.name: head ? modelData.heading : modelData.label + (modelData.detail ? ", " + modelData.detail : "")
                    Accessible.onPressAction: if (!head && modelData.enabled) root.sheets.moreAction(modelData.id)
                    Rectangle {
                        anchors.fill: parent
                        visible: !row.head
                        color: (hover.hovered || row.hot) && modelData.enabled
                            ? Qt.rgba(pal.inkSurface.r, pal.inkSurface.g, pal.inkSurface.b, 0.08) : "transparent"
                    }
                    Text {
                        visible: row.head
                        x: 16
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.verticalCenterOffset: 4
                        text: modelData.heading
                        color: pal.inkMuted
                        font.family: M3Font.family
                        font.pixelSize: 12
                        font.weight: 500
                    }
                    SIcon {
                        visible: !row.head
                        x: 16
                        anchors.verticalCenter: parent.verticalCenter
                        width: 24
                        height: 24
                        name: modelData.icon ? modelData.icon : ""
                        color: modelData.enabled ? pal.inkSurface : pal.disabledInk
                    }
                    Text {
                        visible: !row.head
                        x: 52
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width - 52 - 16 - detail.width
                        text: modelData.label
                        elide: Text.ElideRight
                        color: modelData.enabled ? pal.inkSurface : pal.disabledInk
                        font.family: M3Font.family
                        font.pixelSize: 14
                    }
                    Text {
                        id: detail
                        visible: !row.head && modelData.detail !== ""
                        anchors.right: parent.right
                        anchors.rightMargin: 16
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData.detail
                        color: modelData.enabled ? pal.inkMuted : pal.disabledInk
                        font.family: M3Font.family
                        font.pixelSize: 12
                    }
                    M3FocusRing {
                        anchors.fill: parent
                        anchors.margins: -4
                        extra: row.hot && !row.head
                        target: root
                        ring: pal.focusRing
                        ringRadius: 8
                    }
                    HoverHandler { id: hover }
                    TapHandler {
                        enabled: !row.head && modelData.enabled
                        onTapped: root.sheets.moreAction(modelData.id)
                    }
                }
            }
        }
    }

    Accessible.role: Accessible.PopupMenu
    Accessible.name: "More"
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Down || event.key === Qt.Key_Tab) {
            root.step(1)
            event.accepted = true
        } else if (event.key === Qt.Key_Up || event.key === Qt.Key_Backtab) {
            root.step(-1)
            event.accepted = true
        } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space) {
            if (root.usable(root.cursor))
                root.sheets.moreAction(root.entries[root.cursor].id)
            event.accepted = true
        } else if (event.key === Qt.Key_Escape) {
            root.closeRequested()
            event.accepted = true
        }
    }
}
