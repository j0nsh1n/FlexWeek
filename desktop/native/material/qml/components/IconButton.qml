import QtQuick

Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool small: false
    // A round outline of this width around the icon, as the done circle on a Week block draws it
    // (0: none). The button keeps its own click target; the hover, press and focus rings hug the circle.
    property int ring: 0
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
    readonly property real halo: root.ring > 0 ? root.ring + 8 : root.side

    Rectangle {
        id: shape
        objectName: "shape"
        anchors.fill: parent
        radius: width / 2
        color: "transparent"
    }
    Rectangle {
        objectName: "ringOutline"
        visible: root.ring > 0
        anchors.centerIn: parent
        width: root.ring
        height: root.ring
        radius: width / 2
        color: "transparent"
        border.width: root.highContrast ? 1.5 : 1
        border.color: root.enabled ? palette.outline : palette.disabledInk
    }
    M3StateLayer {
        anchors.centerIn: parent
        width: root.halo
        height: root.halo
        radius: width / 2
        color: palette.inkSurface
        hovered: hover.hovered && root.enabled
        down: (tap.pressed || root.keyDown) && root.enabled
        reduceMotion: root.reduceMotion
    }
    M3FocusRing {
        anchors.centerIn: parent
        width: root.ring > 0 ? root.halo : root.halo + 8
        height: width
        ring: palette.focusRing
        ringRadius: width / 2
    }
    M3Icon {
        anchors.centerIn: parent
        name: root.icon
        width: root.ring > 0 ? Math.round(root.ring * 0.7) : (root.small ? 20 : 24)
        height: width
        color: root.ink
    }

    HoverHandler {
        id: hover
        enabled: root.enabled
        cursorShape: root.ring > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
    }
    TapHandler { id: tap; enabled: root.enabled; onTapped: root.clicked() }
    activeFocusOnTab: root.enabled
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
