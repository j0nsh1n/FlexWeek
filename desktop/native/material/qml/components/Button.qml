import QtQuick

Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    // filled, tonal, outlined, or text.
    property string kind: "filled"
    property string text: "Button"
    property string icon: ""
    property string accessName: ""
    // A quiet button that stays readable while disabled: muted ink at full opacity, not the 38 % disabled ink.
    property bool mutedWhenDisabled: false
    signal clicked()

    readonly property bool quiet: kind === "text"
    readonly property int padH: quiet ? 12 : 24
    height: 40
    implicitHeight: 40
    implicitWidth: label.implicitWidth + (icon !== "" ? 26 : 0) + padH * 2
    width: implicitWidth

    M3Palette { id: palette; theme: root.theme }
    property bool keyDown: false

    readonly property color fill: {
        if (!root.enabled)
            return root.quiet ? "transparent" : palette.disabledFill
        if (root.kind === "filled")
            return palette.primary
        if (root.kind === "tonal")
            return palette.secondaryContainer
        return "transparent"
    }
    readonly property color ink: {
        if (!root.enabled)
            return root.mutedWhenDisabled ? palette.inkMuted : palette.disabledInk
        if (root.kind === "filled")
            return palette.inkPrimary
        if (root.kind === "tonal")
            return palette.inkSecondaryContainer
        return palette.primary
    }

    Rectangle {
        id: shape
        objectName: "shape"
        anchors.fill: parent
        radius: 20
        color: root.fill
        border.width: root.kind === "outlined" ? (root.highContrast ? 1.5 : 1) : 0
        border.color: palette.outline
        Behavior on color {
            ColorAnimation {
                duration: root.reduceMotion ? 0 : 200
                easing.type: Easing.BezierSpline
                easing.bezierCurve: [0.2, 0, 0, 1, 1, 1]
            }
        }
    }
    M3StateLayer {
        anchors.fill: parent
        radius: 20
        color: root.ink
        hovered: hover.hovered && root.enabled
        down: (tap.pressed || root.keyDown) && root.enabled
        reduceMotion: root.reduceMotion
    }
    M3FocusRing {
        anchors.fill: parent
        anchors.margins: -4
        shown: root.activeFocus
        ring: palette.primary
        ringRadius: 24
    }
    Row {
        anchors.centerIn: parent
        spacing: 8
        M3Icon {
            visible: root.icon !== ""
            name: root.icon
            width: 18
            height: 18
            color: root.ink
        }
        Text {
            id: label
            objectName: "label"
            text: root.text
            color: root.ink
            font.family: M3Font.family
            font.pixelSize: 14
            font.weight: 500
        }
    }

    HoverHandler { id: hover; enabled: root.enabled }
    TapHandler { id: tap; enabled: root.enabled; onTapped: root.clicked() }
    activeFocusOnTab: root.enabled
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
            var fire = root.keyDown && root.enabled
            root.keyDown = false
            event.accepted = true
            if (fire)
                Qt.callLater(function() { root.clicked() })
        }
    }
}
