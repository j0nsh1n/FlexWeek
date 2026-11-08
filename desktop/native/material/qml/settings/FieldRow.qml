import QtQuick
import components 1.0

// A title, a helper line, a text field and a Save button. The error under it comes from the bridge.
Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool showDivider: false
    property string key: ""
    property string title: ""
    property string subtitle: ""
    property string text: ""
    property string placeholder: ""
    property string error: ""
    property string saveText: "Save"
    signal submitted(string value)
    objectName: "row_" + key

    readonly property int padV: density === "compact" ? 10 : 16
    implicitHeight: padV * 2 + M3Font.px(24) + (subtitle === "" ? 0 : M3Font.px(20)) + 8 + 56 + (error === "" ? 0 : M3Font.px(20))
    height: implicitHeight

    M3Palette { id: palette; theme: root.theme }

    Rectangle {
        visible: root.showDivider
        width: parent.width
        height: root.highContrast ? 1.5 : 1
        color: root.highContrast ? palette.outline : palette.outlineVariant
    }
    Column {
        x: 16
        y: root.padV
        width: root.width - 32
        spacing: 0
        Text {
            width: parent.width
            height: M3Font.px(24)
            verticalAlignment: Text.AlignVCenter
            text: root.title
            color: palette.inkSurface
            font.family: M3Font.family
            font.pixelSize: M3Font.px(16)
            font.weight: 500
        }
        Text {
            width: parent.width
            height: M3Font.px(20)
            visible: root.subtitle !== ""
            text: root.subtitle
            color: palette.inkMuted
            font.family: M3Font.family
            font.pixelSize: M3Font.px(14)
            elide: Text.ElideRight
        }
        Item { width: 1; height: 8 }
        Row {
            spacing: 12
            OutlinedField {
                id: field
                objectName: root.key
                width: root.width - 32 - saveButton.width - 12
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                label: root.title
                text: root.text
                placeholder: root.placeholder
                accessName: root.title
            }
            Button {
                id: saveButton
                objectName: root.key + "Save"
                y: 8 + (48 - height) / 2
                theme: root.theme
                density: root.density
                reduceMotion: root.reduceMotion
                highContrast: root.highContrast
                kind: "tonal"
                text: root.saveText
                accessName: root.saveText + " " + root.title
                onClicked: root.submitted(field.text)
            }
        }
        Text {
            objectName: root.key + "Error"
            width: parent.width
            height: M3Font.px(20)
            visible: root.error !== ""
            text: root.error
            color: palette.error
            font.family: M3Font.family
            font.pixelSize: M3Font.px(14)
        }
    }
}
