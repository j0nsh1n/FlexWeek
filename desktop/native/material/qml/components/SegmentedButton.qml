import QtQuick

Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property var choices: []
    property string current: ""
    property string accessName: "Choose one"
    signal selected(string value)

    implicitHeight: 40
    height: 40
    implicitWidth: row.implicitWidth
    width: implicitWidth

    M3Palette { id: palette; theme: root.theme }
    // A repeater delegate has its own `palette`, so colours are copied onto the root.
    readonly property color lineColor: palette.outline
    readonly property color activeFill: palette.secondaryContainer
    readonly property color activeInk: palette.inkSecondaryContainer
    readonly property color offInk: palette.inkMuted
    property bool keyDown: false

    function indexOfCurrent() {
        for (var i = 0; i < choices.length; i++) {
            if (choices[i].value === current)
                return i
        }
        return 0
    }

    function choose(index) {
        if (!enabled || choices.length === 0)
            return
        var next = (index + choices.length) % choices.length
        selected(choices[next].value)
    }

    Rectangle {
        id: shape
        objectName: "shape"
        anchors.fill: parent
        radius: 6
        color: "transparent"
        border.width: 0
        border.color: root.lineColor
        clip: true
        Row {
            id: row
            height: 40
            spacing: 0
            Repeater {
                model: root.choices
                delegate: Item {
                    id: segment
                    readonly property bool on: modelData.value === root.current
                    width: 12 + (on ? 24 : 0) + caption.implicitWidth + 12
                    height: 40
                    Rectangle {
                        anchors.fill: parent
                        radius: height / 2
                        color: segment.on ? root.activeFill : "transparent"
                    }
                    Row {
                        anchors.centerIn: parent
                        spacing: 6
                        M3Icon {
                            objectName: segment.on ? "segmentCheck" : ""
                            visible: segment.on
                            name: "check"
                            width: 18
                            height: 18
                            color: root.activeInk
                        }
                        Text {
                            id: caption
                            text: modelData.label
                            color: segment.on ? root.activeInk : root.offInk
                            font.family: M3Font.family
                            font.pixelSize: 14
                            font.weight: 500
                        }
                    }
                    TapHandler {
                        enabled: root.enabled
                        onTapped: root.choose(index)
                    }
                }
            }
        }
    }
    M3StateLayer {
        anchors.fill: parent
        radius: 6
        color: palette.inkSurface
        hovered: hover.hovered && root.enabled
        down: (root.keyDown) && root.enabled
        reduceMotion: root.reduceMotion
    }
    M3FocusRing {
        anchors.fill: parent
        anchors.margins: -4
        ring: palette.focusRing
        ringRadius: 10
    }

    HoverHandler { id: hover; enabled: root.enabled }
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: accessName
    Accessible.onPressAction: root.choose(root.indexOfCurrent())
    Keys.onPressed: (event) => {
        if (!root.enabled)
            return
        if (event.key === Qt.Key_Right || event.key === Qt.Key_Down) {
            root.choose(root.indexOfCurrent() + 1)
            event.accepted = true
        } else if (event.key === Qt.Key_Left || event.key === Qt.Key_Up) {
            root.choose(root.indexOfCurrent() - 1)
            event.accepted = true
        } else if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            root.keyDown = true
            event.accepted = true
        }
    }
    Keys.onReleased: (event) => {
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            root.keyDown = false
            event.accepted = true
        }
    }
}
