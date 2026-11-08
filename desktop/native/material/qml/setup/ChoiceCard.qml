import QtQuick
import components 1.0

// One choice out of several: a card that shows what it does and, when picked, a check and the
// secondary container fill. Space and Return pick it.
Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property string title: ""
    property string note: ""
    property bool selected: false
    property string accessName: ""
    signal chosen()

    implicitWidth: 320
    implicitHeight: Math.max(64, words.implicitHeight + 24)
    height: implicitHeight

    M3Palette { id: palette; theme: root.theme }
    property bool keyDown: false

    Rectangle {
        id: shape
        anchors.fill: parent
        radius: 8
        color: root.selected ? palette.secondaryContainer : palette.surfaceContainerLow
        border.width: root.selected ? 2 : (root.highContrast ? 1.5 : 1)
        border.color: root.selected ? palette.primary : palette.outlineVariant
        Behavior on color {
            ColorAnimation { duration: root.reduceMotion ? 0 : 200 }
        }
    }
    M3StateLayer {
        anchors.fill: parent
        radius: 8
        color: root.selected ? palette.inkSecondaryContainer : palette.inkSurface
        hovered: hover.hovered && root.enabled
        down: (tap.pressed || root.keyDown) && root.enabled
        reduceMotion: root.reduceMotion
    }
    M3FocusRing {
        anchors.fill: parent
        anchors.margins: -4
        ring: palette.focusRing
        ringRadius: 12
    }
    Item {
        id: mark
        x: 16
        anchors.verticalCenter: parent.verticalCenter
        width: 24
        height: 24
        M3Icon {
            visible: root.selected
            anchors.fill: parent
            name: "check"
            color: palette.primary
        }
        Rectangle {
            visible: !root.selected
            anchors.centerIn: parent
            width: 20
            height: 20
            radius: 10
            color: "transparent"
            border.width: 2
            border.color: palette.outline
        }
    }
    Column {
        id: words
        anchors.left: mark.right
        anchors.leftMargin: 16
        anchors.right: parent.right
        anchors.rightMargin: 16
        anchors.verticalCenter: parent.verticalCenter
        spacing: 2
        Text {
            width: parent.width
            text: root.title
            wrapMode: Text.WordWrap
            color: root.selected ? palette.inkSecondaryContainer : palette.inkSurface
            font.family: M3Font.family
            font.pixelSize: M3Font.px(16)
            font.weight: 500
        }
        Text {
            visible: root.note !== ""
            width: parent.width
            text: root.note
            wrapMode: Text.WordWrap
            color: root.selected ? palette.inkSecondaryContainer : palette.inkMuted
            font.family: M3Font.family
            font.pixelSize: M3Font.px(14)
        }
    }

    HoverHandler { id: hover; enabled: root.enabled }
    TapHandler { id: tap; enabled: root.enabled; onTapped: root.chosen() }
    activeFocusOnTab: true
    Accessible.role: Accessible.RadioButton
    Accessible.name: accessName !== "" ? accessName : title
    Accessible.description: note
    Accessible.checkable: true
    Accessible.checked: selected
    Accessible.onPressAction: root.chosen()
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            root.keyDown = true
            event.accepted = true
        }
    }
    Keys.onReleased: (event) => {
        if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            if (root.keyDown)
                root.chosen()
            root.keyDown = false
            event.accepted = true
        }
    }
}
