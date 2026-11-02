import QtQuick

Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool open: false
    property string title: ""
    property string body: ""
    property string accessName: ""
    signal dismissed()

    anchors.fill: parent
    visible: open
    z: 20

    M3Palette { id: palette; theme: root.theme }

    function close() {
        open = false
        dismissed()
    }

    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 0.32
        TapHandler { onTapped: root.close() }
    }
    Rectangle {
        id: card
        objectName: "sheetCard"
        width: parent.width
        height: column.y + column.implicitHeight + 24
        anchors.bottom: parent.bottom
        color: palette.surfaceContainerHigh
        topLeftRadius: 28
        topRightRadius: 28
        bottomLeftRadius: 0
        bottomRightRadius: 0
        clip: true
        Column {
            id: column
            y: 12
            width: parent.width
            spacing: 16
            Item {
                width: parent.width
                height: 4
                Rectangle {
                    x: (parent.width - 32) / 2
                    width: 32
                    height: 4
                    radius: 2
                    color: palette.outline
                }
            }
            Text {
                x: 24
                width: parent.width - 48
                text: root.title
                color: palette.inkSurface
                font.family: M3Font.family
                font.pixelSize: 24
                font.weight: 400
                wrapMode: Text.WordWrap
            }
            Text {
                x: 24
                width: parent.width - 48
                text: root.body
                color: palette.inkMuted
                font.family: M3Font.family
                font.pixelSize: 14
                wrapMode: Text.WordWrap
            }
        }
    }

    activeFocusOnTab: open
    Accessible.role: Accessible.Dialog
    Accessible.name: accessName !== "" ? accessName : title
    onOpenChanged: if (open) forceActiveFocus()
    Keys.onEscapePressed: (event) => {
        root.close()
        event.accepted = true
    }
}
