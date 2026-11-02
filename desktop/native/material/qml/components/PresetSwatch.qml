import QtQuick

Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property color quadrantPrimary: "#425e91"
    property color quadrantTertiary: "#705574"
    property color quadrantSecondary: "#dae2f9"
    property color quadrantPrimaryContainer: "#d7e2ff"
    property string label: ""
    property bool selected: false
    property string accessName: ""
    signal clicked()

    implicitWidth: 64
    implicitHeight: 48 + (label === "" ? 0 : 24)
    width: implicitWidth
    height: implicitHeight

    M3Palette { id: palette; theme: root.theme }
    property bool keyDown: false

    Item {
        id: disc
        objectName: "swatchDisc"
        width: 48
        height: 48
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        Canvas {
            id: canvas
            anchors.fill: parent
            onPaint: {
                var ctx = getContext("2d")
                var cx = width / 2
                var cy = height / 2
                var radius = width / 2
                ctx.clearRect(0, 0, width, height)
                ctx.beginPath()
                ctx.arc(cx, cy, radius, 0, Math.PI * 2)
                ctx.clip()
                var parts = [root.quadrantPrimary, root.quadrantTertiary, root.quadrantSecondary, root.quadrantPrimaryContainer]
                for (var i = 0; i < 4; i++) {
                    ctx.beginPath()
                    ctx.moveTo(cx, cy)
                    ctx.arc(cx, cy, radius, -Math.PI / 2 + i * Math.PI / 2, -Math.PI / 2 + (i + 1) * Math.PI / 2)
                    ctx.closePath()
                    ctx.fillStyle = parts[i]
                    ctx.fill()
                }
            }
        }
        onWidthChanged: canvas.requestPaint()
        Component.onCompleted: canvas.requestPaint()
    }
    // Repaint when a quadrant colour changes.
    onQuadrantPrimaryChanged: disc.children[0].requestPaint()
    onQuadrantTertiaryChanged: disc.children[0].requestPaint()
    onQuadrantSecondaryChanged: disc.children[0].requestPaint()
    onQuadrantPrimaryContainerChanged: disc.children[0].requestPaint()

    M3FocusRing {
        anchors.fill: disc
        anchors.margins: -4
        shown: root.selected || root.activeFocus
        ring: palette.primary
        ringRadius: 28
    }
    Rectangle {
        objectName: "swatchBadge"
        visible: root.selected
        width: 22
        height: 22
        radius: 11
        anchors.centerIn: disc
        color: palette.inverseSurface
        M3Icon {
            anchors.centerIn: parent
            name: "check"
            width: 16
            height: 16
            color: palette.inverseOnSurface
        }
    }
    Text {
        visible: root.label !== ""
        anchors.top: disc.bottom
        anchors.topMargin: 8
        anchors.horizontalCenter: parent.horizontalCenter
        text: root.label
        color: palette.inkSurface
        font.family: M3Font.family
        font.pixelSize: 12
        font.weight: 500
    }
    M3StateLayer {
        anchors.fill: disc
        radius: 24
        color: palette.inkSurface
        hovered: hover.hovered && root.enabled && !root.selected
        down: (tap.pressed || root.keyDown) && root.enabled
        reduceMotion: root.reduceMotion
    }

    HoverHandler { id: hover; enabled: root.enabled }
    TapHandler { id: tap; enabled: root.enabled; onTapped: root.clicked() }
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: accessName !== "" ? accessName : (label !== "" ? label : "Preset")
    Accessible.checkable: true
    Accessible.checked: selected
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
