import QtQuick

Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool checked: false
    property string accessName: "Switch"
    signal toggled(bool on)

    width: 52
    height: 32
    implicitWidth: 52
    implicitHeight: 32

    M3Palette { id: palette; theme: root.theme }
    property bool keyDown: false
    // Skip the first layout so a switch does not slide in from the off position.
    property bool animate: false
    Component.onCompleted: animate = true

    function toggle() {
        if (!enabled)
            return
        checked = !checked
        toggled(checked)
    }

    Rectangle {
        id: track
        objectName: "shape"
        anchors.fill: parent
        radius: 16
        color: root.checked ? palette.primary : palette.surfaceContainerHighest
        border.width: 2
        border.color: root.checked ? palette.primary : palette.outline
        Behavior on color {
            enabled: root.animate && !root.reduceMotion
            ColorAnimation {
                duration: 200
                easing.type: Easing.BezierSpline
                easing.bezierCurve: [0.2, 0, 0, 1, 1, 1]
            }
        }
        Behavior on border.color {
            enabled: root.animate && !root.reduceMotion
            ColorAnimation { duration: 200 }
        }
    }

    // Outer box is 52 by 32 and includes the 2px border. The thumb's visual
    // inset matches the mockup: off at 8,8 size 16; on at 24,4 size 24.
    Rectangle {
        id: thumb
        objectName: "switchThumb"
        x: root.checked ? 24 : 8
        y: root.checked ? 4 : 8
        width: root.checked ? 24 : 16
        height: width
        radius: width / 2
        color: root.checked ? palette.inkPrimary : palette.outline
        Behavior on x {
            enabled: root.animate && !root.reduceMotion
            NumberAnimation { duration: 300; easing.type: Easing.BezierSpline; easing.bezierCurve: [0.2, 0, 0, 1, 1, 1] }
        }
        Behavior on y {
            enabled: root.animate && !root.reduceMotion
            NumberAnimation { duration: 300; easing.type: Easing.BezierSpline; easing.bezierCurve: [0.2, 0, 0, 1, 1, 1] }
        }
        Behavior on width {
            enabled: root.animate && !root.reduceMotion
            NumberAnimation { duration: 300; easing.type: Easing.BezierSpline; easing.bezierCurve: [0.2, 0, 0, 1, 1, 1] }
        }
        M3Icon {
            anchors.centerIn: parent
            name: "check"
            width: 16
            height: 16
            color: palette.inkPrimaryContainer
            opacity: root.checked ? 1 : 0
        }
    }

    Rectangle {
        z: 2
        width: 40
        height: 40
        radius: 20
        x: thumb.x + thumb.width / 2 - 20
        y: thumb.y + thumb.height / 2 - 20
        color: root.checked ? palette.inkPrimary : palette.inkSurface
        opacity: !root.enabled ? 0 : (tap.pressed || root.keyDown) ? 0.12 : hover.hovered ? 0.08 : 0
    }
    M3FocusRing {
        z: 3
        anchors.fill: parent
        anchors.margins: -4
        shown: root.activeFocus
        ring: palette.primary
        ringRadius: 20
    }

    HoverHandler { id: hover; enabled: root.enabled }
    TapHandler { id: tap; enabled: root.enabled; onTapped: root.toggle() }
    activeFocusOnTab: true
    Accessible.role: Accessible.Switch
    Accessible.name: accessName
    Accessible.checkable: true
    Accessible.checked: root.checked
    Accessible.onPressAction: root.toggle()
    Accessible.onToggleAction: root.toggle()
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
            if (root.keyDown)
                root.toggle()
            root.keyDown = false
            event.accepted = true
        }
    }
}
