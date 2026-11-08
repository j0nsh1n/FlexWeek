import QtQuick

Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property string icon: "add"
    property string text: "Add homework"
    property string accessName: ""
    property bool railItem: true
    property bool pinned: false
    property int railGap: 16
    signal clicked()

    height: 56
    implicitHeight: 56
    implicitWidth: row.implicitWidth + 36
    width: implicitWidth

    M3Palette { id: palette; theme: root.theme }
    property bool keyDown: false

    Rectangle {
        id: shape
        objectName: "shape"
        anchors.fill: parent
        radius: 6
        color: root.enabled ? palette.card : palette.disabledFill
        border.width: root.highContrast ? 1.5 : 1
        border.color: palette.edge
    }
    M3StateLayer {
        anchors.fill: parent
        radius: 6
        color: root.enabled ? palette.primary : "transparent"
        hovered: hover.hovered && root.enabled
        down: (tap.pressed || root.keyDown) && root.enabled
        reduceMotion: root.reduceMotion
    }
    M3FocusRing {
        anchors.fill: parent
        anchors.margins: -4
        ring: palette.focusRing
        ringRadius: 10
    }
    Row {
        id: row
        anchors.centerIn: parent
        spacing: 12
        M3Icon {
            name: root.icon
            width: 24
            height: 24
            color: root.enabled ? palette.primary : palette.disabledInk
        }
        Text {
            text: root.text
            color: root.enabled ? palette.primary : palette.disabledInk
            font.family: M3Font.family
            font.pixelSize: M3Font.px(14)
            font.weight: 500
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    HoverHandler { id: hover; enabled: root.enabled }
    TapHandler { id: tap; enabled: root.enabled; onTapped: root.clicked() }
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: accessName !== "" ? accessName : text
    Accessible.onPressAction: if (root.enabled) root.clicked()
    Keys.onPressed: (event) => {
        if (!root.enabled)
            return
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            root.keyDown = true
            event.accepted = true
        }
    }
    Keys.onReleased: (event) => {
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            if (root.keyDown && root.enabled)
                root.clicked()
            root.keyDown = false
            event.accepted = true
        }
    }
}
