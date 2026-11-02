import QtQuick

Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property string icon: "calendar_view_week"
    property string label: "Week"
    property string destinationId: ""
    property bool selected: false
    property bool pinned: false
    property bool bar: false
    property bool railItem: true
    property int railGap: 4
    property string accessName: ""
    signal activated()

    implicitWidth: bar ? 64 : 72
    implicitHeight: bar ? 80 : 52
    width: implicitWidth
    height: implicitHeight

    M3Palette { id: palette; theme: root.theme }
    property bool keyDown: false

    Item {
        id: mark
        objectName: "indicator"
        width: 56
        height: 32
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: root.bar ? 14 : 0
        Rectangle {
            anchors.fill: parent
            radius: 16
            color: palette.secondaryContainer
            scale: root.selected ? 1 : 0
            transformOrigin: Item.Center
            Behavior on scale {
                NumberAnimation {
                    duration: root.reduceMotion ? 0 : 300
                    easing.type: Easing.BezierSpline
                    easing.bezierCurve: [0.2, 0, 0, 1, 1, 1]
                }
            }
        }
        M3StateLayer {
            anchors.fill: parent
            radius: 16
            color: root.selected ? palette.inkSecondaryContainer : palette.inkSurface
            hovered: hover.hovered && root.enabled
            down: (tap.pressed || root.keyDown) && root.enabled
            reduceMotion: root.reduceMotion
        }
        M3Icon {
            anchors.centerIn: parent
            name: root.icon
            width: 24
            height: 24
            color: root.selected ? palette.inkSecondaryContainer : palette.inkMuted
        }
    }
    Text {
        id: caption
        anchors.top: mark.bottom
        anchors.topMargin: 4
        anchors.horizontalCenter: parent.horizontalCenter
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
        text: root.label
        color: root.selected ? palette.inkSurface : palette.inkMuted
        font.family: M3Font.family
        font.pixelSize: 12
        font.weight: 500
    }
    M3FocusRing {
        anchors.fill: mark
        anchors.margins: -4
        shown: root.activeFocus
        ring: palette.primary
        ringRadius: 20
    }

    HoverHandler { id: hover; enabled: root.enabled }
    TapHandler {
        id: tap
        enabled: root.enabled
        onTapped: root.activated()
    }
    activeFocusOnTab: true
    Accessible.role: Accessible.PageTab
    Accessible.name: accessName !== "" ? accessName : label
    Accessible.checkable: true
    Accessible.checked: selected
    Accessible.onPressAction: if (root.enabled) root.activated()
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
                root.activated()
            root.keyDown = false
            event.accepted = true
        }
    }
}
