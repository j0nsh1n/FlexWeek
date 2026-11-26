import QtQuick
import components 1.0

// A group title in primary, with an optional icon on the left and Reset on the right.
// Counts as a row for the group's dividers.
Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool showDivider: false
    property string title: ""
    property string icon: ""
    property string resetKey: ""
    signal reset()
    implicitHeight: 48
    height: 48
    objectName: "header_" + title.toLowerCase()

    M3Palette { id: palette; theme: root.theme }
    Rectangle {
        visible: root.showDivider
        width: parent.width
        height: 1
        color: palette.outlineVariant
    }
    Row {
        x: 16
        anchors.verticalCenter: parent.verticalCenter
        spacing: 8
        M3Icon {
            visible: root.icon !== ""
            name: root.icon
            width: 18
            height: 18
            anchors.verticalCenter: parent.verticalCenter
            color: palette.primary
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.title
            color: palette.primary
            font.family: M3Font.heading
            font.pixelSize: M3Font.px(15)
            font.weight: 600
        }
    }
    Button {
        objectName: "reset_" + root.resetKey
        visible: root.resetKey !== ""
        anchors.right: parent.right
        anchors.rightMargin: 4
        anchors.verticalCenter: parent.verticalCenter
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        kind: "text"
        text: "Reset"
        accessName: "Reset " + root.title
        onClicked: root.reset()
    }
}
