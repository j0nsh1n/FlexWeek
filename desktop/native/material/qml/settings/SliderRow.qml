import QtQuick
import components 1.0

// A labelled slider. `value` follows the bridge; dragging or arrow keys report through `moved`.
Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool showDivider: false
    property string key: ""
    property string title: ""
    property string unit: ""
    property real from: 0
    property real to: 100
    property real step: 1
    property real value: 0
    property int decimals: 0
    signal moved(real value)
    objectName: "row_" + key

    implicitHeight: 52 + M3Font.px(24)
    height: implicitHeight

    M3Palette { id: palette; theme: root.theme }
    readonly property real span: Math.max(0.0001, to - from)
    readonly property real shown: Math.max(from, Math.min(to, value))
    property bool dragging: false

    function snap(raw) {
        var n = Math.round((raw - from) / step) * step + from
        return Math.max(from, Math.min(to, Number(n.toFixed(4))))
    }
    function nudge(delta) {
        var next = snap(shown + delta * step)
        if (next !== shown)
            moved(next)
    }

    Rectangle {
        visible: root.showDivider
        width: parent.width
        height: root.highContrast ? 1.5 : 1
        color: root.highContrast ? palette.outline : palette.outlineVariant
    }
    Text {
        x: 16
        y: 10
        height: M3Font.px(24)
        verticalAlignment: Text.AlignVCenter
        text: root.title
        color: palette.inkSurface
        font.family: M3Font.family
        font.pixelSize: M3Font.px(16)
        font.weight: 500
    }
    Text {
        objectName: root.key + "Value"
        anchors.right: parent.right
        anchors.rightMargin: 16
        y: 10
        height: M3Font.px(24)
        verticalAlignment: Text.AlignVCenter
        text: root.shown.toFixed(root.decimals) + root.unit
        color: palette.primary
        font.family: M3Font.family
        font.pixelSize: M3Font.px(14)
        font.weight: 500
    }
    Item {
        id: slider
        objectName: root.key
        x: 16
        y: 14 + M3Font.px(24)
        width: root.width - 32
        height: 28
        activeFocusOnTab: true
        Accessible.role: Accessible.Slider
        Accessible.name: root.title
        Accessible.description: root.shown.toFixed(root.decimals) + root.unit
        Accessible.onIncreaseAction: root.nudge(1)
        Accessible.onDecreaseAction: root.nudge(-1)
        Keys.onPressed: (event) => {
            if (event.key === Qt.Key_Right || event.key === Qt.Key_Up) {
                root.nudge(1)
                event.accepted = true
            } else if (event.key === Qt.Key_Left || event.key === Qt.Key_Down) {
                root.nudge(-1)
                event.accepted = true
            }
        }
        Rectangle {
            id: rail
            y: 12
            width: parent.width
            height: 4
            radius: 2
            color: palette.secondaryContainer
        }
        Rectangle {
            y: 12
            width: knob.x + knob.width / 2
            height: 4
            radius: 2
            color: palette.primary
        }
        Rectangle {
            id: knob
            width: 20
            height: 20
            radius: 10
            y: 4
            x: (slider.width - width) * (root.shown - root.from) / root.span
            color: palette.primary
        }
        M3FocusRing {
            anchors.fill: knob
            anchors.margins: -4
            target: slider
            ring: palette.focusRing
            ringRadius: 14
        }
        MouseArea {
            anchors.fill: parent
            onPressed: (mouse) => { slider.forceActiveFocus(); root.dragging = true; set(mouse.x) }
            onPositionChanged: (mouse) => { if (pressed) set(mouse.x) }
            onReleased: root.dragging = false
            function set(px) {
                var ratio = Math.max(0, Math.min(1, (px - knob.width / 2) / Math.max(1, slider.width - knob.width)))
                var next = root.snap(root.from + ratio * root.span)
                if (next !== root.shown)
                    root.moved(next)
            }
        }
    }
}
