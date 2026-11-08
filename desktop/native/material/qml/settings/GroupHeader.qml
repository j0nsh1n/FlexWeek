import QtQuick
import components 1.0

// A group title in primary, with an optional Reset on the right. Counts as a row for the group's dividers.
Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool showDivider: false
    property string title: ""
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
    Text {
        x: 16
        anchors.verticalCenter: parent.verticalCenter
        text: root.title
        color: palette.primary
        font.family: M3Font.family
        font.pixelSize: M3Font.px(16)
        font.weight: 500
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
