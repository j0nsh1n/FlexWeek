import QtQuick

FocusScope {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool open: false
    property string title: ""
    property string body: ""
    property string confirmText: "Save"
    property string dismissText: "Cancel"
    property string accessName: ""
    signal confirmed()
    signal dismissed()

    anchors.fill: parent
    visible: open
    focus: open
    z: 20

    M3Palette { id: palette; theme: root.theme }

    function close() {
        open = false
        dismissed()
    }

    function accept() {
        open = false
        confirmed()
    }

    function cycle(step) {
        FocusCycle.take(FocusCycle.nextItem([card], step, Window.activeFocusItem), step)
    }

    function focusFirst() {
        dismissButton.forceActiveFocus()
    }

    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 0.32
        TapHandler { onTapped: root.close() }
    }
    Rectangle {
        id: card
        objectName: "dialogCard"
        width: Math.min(440, Math.max(0, root.width - 32))
        height: column.implicitHeight + 48
        radius: 28
        anchors.centerIn: parent
        color: palette.surfaceContainerHigh
        clip: true
        Column {
            id: column
            x: 24
            y: 24
            width: card.width - 48
            spacing: 16
            Text {
                width: parent.width
                text: root.title
                color: palette.inkSurface
                font.family: M3Font.family
                font.pixelSize: 24
                font.weight: 400
                wrapMode: Text.WordWrap
            }
            Text {
                width: parent.width
                text: root.body
                color: palette.inkMuted
                font.family: M3Font.family
                font.pixelSize: 14
                font.weight: 400
                wrapMode: Text.WordWrap
            }
            Item {
                width: parent.width
                height: actions.implicitHeight
                Row {
                    id: actions
                    anchors.right: parent.right
                    spacing: 8
                    Button {
                        id: dismissButton
                        objectName: "dialogDismiss"
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        kind: "text"
                        text: root.dismissText
                        accessName: root.dismissText
                        onClicked: root.close()
                    }
                    Button {
                        objectName: "dialogConfirm"
                        theme: root.theme
                        density: root.density
                        reduceMotion: root.reduceMotion
                        highContrast: root.highContrast
                        kind: "filled"
                        text: root.confirmText
                        accessName: root.confirmText
                        onClicked: root.accept()
                    }
                }
            }
        }
    }
    M3FocusRing {
        anchors.fill: card
        anchors.margins: -4
        shown: root.activeFocus
        ring: palette.primary
        ringRadius: 32
    }

    Accessible.role: Accessible.Dialog
    Accessible.name: accessName !== "" ? accessName : title
    onOpenChanged: if (open) Qt.callLater(root.focusFirst)
    Keys.onEscapePressed: (event) => {
        root.close()
        event.accepted = true
    }
    Keys.priority: Keys.BeforeItem
    Keys.onTabPressed: (event) => {
        root.cycle(1)
        event.accepted = true
    }
    Keys.onBacktabPressed: (event) => {
        root.cycle(-1)
        event.accepted = true
    }
}
