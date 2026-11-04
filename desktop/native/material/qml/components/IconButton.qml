import QtQuick

Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool small: false
    property string icon: "more_vert"
    property string accessName: "More"
    signal clicked()

    readonly property int side: small ? 32 : 48
    width: side
    height: side
    implicitWidth: side
    implicitHeight: side

    M3Palette { id: palette; theme: root.theme }
    property bool keyDown: false
    readonly property color ink: root.enabled ? palette.inkMuted : palette.disabledInk

    Rectangle {
        id: shape
        objectName: "shape"
        anchors.fill: parent
        radius: width / 2
        color: "transparent"
    }
    M3StateLayer {
        anchors.fill: parent
        radius: width / 2
        color: palette.inkSurface
        hovered: hover.hovered && root.enabled
        down: (tap.pressed || root.keyDown) && root.enabled
        reduceMotion: root.reduceMotion
    }
    M3FocusRing {
        anchors.fill: parent
        anchors.margins: -4
        shown: root.activeFocus
        ring: palette.primary
        ringRadius: root.side / 2 + 4
    }
    M3Icon {
        anchors.centerIn: parent
        name: root.icon
        width: root.small ? 20 : 24
        height: root.small ? 20 : 24
        color: root.ink
    }

    HoverHandler { id: hover; enabled: root.enabled }
    TapHandler { id: tap; enabled: root.enabled; onTapped: root.clicked() }
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: accessName
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
            var fire = root.keyDown && root.enabled
            root.keyDown = false
            event.accepted = true
            if (fire)
                Qt.callLater(function() { root.clicked() })
        }
    }
}
