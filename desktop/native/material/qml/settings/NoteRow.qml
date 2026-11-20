import QtQuick
import components 1.0

// A line of help inside a group: what a setting means, or why it cannot be changed. `problem` draws it as an error.
Item {
    id: root
    property var theme: Ui.theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool showDivider: false
    property string text: ""
    property bool problem: false
    property string key: ""
    objectName: "note_" + key

    implicitHeight: label.implicitHeight + 16
    height: implicitHeight

    M3Palette { id: palette; theme: root.theme }

    Rectangle {
        visible: root.showDivider
        width: parent.width
        height: root.highContrast ? 1.5 : 1
        color: root.highContrast ? palette.outline : palette.outlineVariant
    }
    Text {
        id: label
        x: 16
        y: 8
        width: root.width - 32
        text: root.text
        color: root.problem ? palette.error : palette.inkMuted
        font.family: M3Font.family
        font.pixelSize: M3Font.px(14)
        wrapMode: Text.WordWrap
    }
}
