import QtQuick
import components 1.0

// One choice out of several: an elevated M3 card that shows what it does and, when picked,
// a check badge and the secondary container fill. Space and Return pick it.
Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property string title: ""
    property string note: ""
    // A short label under the title, such as Recommended.
    property string tag: ""
    property bool selected: false
    property string accessName: ""
    signal chosen()

    implicitWidth: 260
    implicitHeight: Math.max(68, words.implicitHeight + 24)

    M3Palette { id: palette; theme: root.theme }
    property bool keyDown: false
    readonly property real cardRadius: palette.cornerFor(14)

    Rectangle {
        id: shape
        anchors.fill: parent
        radius: root.cardRadius
        color: root.selected ? palette.secondaryContainer : palette.cardSurface
        border.width: root.selected ? 2 : (root.highContrast ? 1.5 : 1)
        border.color: root.selected ? palette.primary : (root.highContrast ? palette.outline : palette.outlineVariant)
        Behavior on color {
            ColorAnimation { duration: Motion.fade(200, root.reduceMotion) }
        }
    }
    M3StateLayer {
        anchors.fill: parent
        radius: root.cardRadius
        color: root.selected ? palette.inkSecondaryContainer : palette.inkSurface
        hovered: hover.hovered && root.enabled
        down: (tap.pressed || root.keyDown) && root.enabled
        reduceMotion: root.reduceMotion
    }
    M3FocusRing {
        anchors.fill: parent
        anchors.margins: -4
        ring: palette.focusRing
        ringRadius: root.cardRadius + 4
    }
    Item {
        id: mark
        x: 16
        anchors.verticalCenter: parent.verticalCenter
        width: 22
        height: 22
        Rectangle {
            visible: root.selected
            anchors.fill: parent
            radius: 11
            color: palette.primary
            M3Icon {
                anchors.centerIn: parent
                width: 14
                height: 14
                name: "check"
                color: palette.inkPrimary
            }
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
        anchors.leftMargin: 14
        anchors.right: parent.right
        anchors.rightMargin: 16
        anchors.verticalCenter: parent.verticalCenter
        spacing: 4
        Text {
            width: parent.width
            text: root.title
            wrapMode: Text.WordWrap
            color: root.selected ? palette.inkSecondaryContainer : palette.inkSurface
            font.family: M3Font.heading
            font.pixelSize: M3Font.px(15)
            font.weight: 600
        }
        Rectangle {
            visible: root.tag !== ""
            width: tagText.implicitWidth + 16
            height: M3Font.px(20)
            radius: height / 2
            color: root.selected ? palette.cardSurface : palette.primaryContainer
            Text {
                id: tagText
                anchors.centerIn: parent
                text: root.tag
                color: root.selected ? palette.inkSecondaryContainer : palette.inkPrimaryContainer
                font.family: M3Font.family
                font.pixelSize: M3Font.px(11)
                font.weight: 600
            }
        }
        Text {
            visible: root.note !== ""
            width: parent.width
            text: root.note
            wrapMode: Text.WordWrap
            color: root.selected ? palette.inkSecondaryContainer : palette.inkMuted
            font.family: M3Font.family
            font.pixelSize: M3Font.px(13)
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
