import QtQuick

Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool open: true
    property var entries: []
    property string accessName: "Menu"
    signal chosen(int index, string label)
    signal dismissed()

    visible: open
    implicitWidth: 260
    width: 260
    implicitHeight: 16 + entries.length * 44
    height: implicitHeight

    M3Palette { id: palette; theme: root.theme }
    // A repeater delegate has its own `palette`, so the row ink is copied onto the root.
    readonly property color rowInk: palette.inkSurface
    property int cursor: 0

    Rectangle {
        anchors.fill: parent
        anchors.topMargin: 4
        radius: 4
        color: "#4d000000"
        z: -1
    }
    Rectangle {
        id: shape
        objectName: "shape"
        anchors.fill: parent
        radius: 4
        color: palette.surfaceContainer
        border.width: root.highContrast ? 1.5 : 0
        border.color: palette.outlineVariant
        clip: true
        Column {
            y: 8
            width: parent.width
            spacing: 0
            Repeater {
                model: root.entries
                delegate: Item {
            Accessible.role: Accessible.MenuItem
            Accessible.name: modelData.label
            Accessible.focused: row.hot
            Accessible.selectable: true
            Accessible.selected: row.hot
            Accessible.onPressAction: {
                root.cursor = index
                root.chosen(index, modelData.label)
            }
                    id: row
                    width: 260
                    height: 44
                    readonly property bool hot: root.cursor === index
                    Rectangle {
                        anchors.fill: parent
                        color: (hover.hovered || row.hot) ? Qt.rgba(root.rowInk.r, root.rowInk.g, root.rowInk.b, 0.08) : "transparent"
                    }
                    M3Icon {
                        id: glyph
                        x: 16
                        y: 10
                        name: modelData.icon === undefined ? "" : modelData.icon
                        visible: modelData.icon !== undefined && modelData.icon !== ""
                        width: 24
                        height: 24
                        color: root.rowInk
                    }
                    Text {
                        x: glyph.visible ? 52 : 16
                        y: (44 - implicitHeight) / 2
                        width: 260 - x - 16
                        text: modelData.label
                        color: root.rowInk
                        font.family: M3Font.family
                        font.pixelSize: 14
                        font.weight: 400
                        elide: Text.ElideRight
                    }
                    HoverHandler { id: hover }
                    TapHandler {
                        onTapped: {
                            root.cursor = index
                            root.chosen(index, modelData.label)
                        }
                    }
                }
            }
        }
    }

    function move(step) {
        if (entries.length === 0)
            return
        cursor = (cursor + step + entries.length) % entries.length
    }

    activeFocusOnTab: open
    Accessible.role: Accessible.PopupMenu
    Accessible.name: accessName
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Down) {
            root.move(1)
            event.accepted = true
        } else if (event.key === Qt.Key_Up) {
            root.move(-1)
            event.accepted = true
        } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space) {
            if (root.entries.length > 0)
                root.chosen(root.cursor, root.entries[root.cursor].label)
            event.accepted = true
        } else if (event.key === Qt.Key_Escape) {
            root.open = false
            root.dismissed()
            event.accepted = true
        }
    }
}
