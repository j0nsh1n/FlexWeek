import QtQuick
import components 1.0

// A colour dial: a swatch and a hex field. Only a whole #rrggbb (or an empty field, meaning the preset's own) is sent.
Item {
    id: root
    property var theme
    property string density: "comfortable"
    property bool reduceMotion: false
    property bool highContrast: false
    property bool showDivider: false
    property string key: ""
    property string title: ""
    property string value: ""
    property string fallback: "#888888"
    signal edited(string value)
    objectName: "row_" + key

    readonly property bool bad: field.text !== "" && !/^#[0-9a-fA-F]{6}$/.test(field.text)
    implicitHeight: 72 + (bad ? 20 : 0)
    height: implicitHeight

    M3Palette { id: palette; theme: root.theme }
    Rectangle {
        visible: root.showDivider
        width: parent.width
        height: root.highContrast ? 1.5 : 1
        color: root.highContrast ? palette.outline : palette.outlineVariant
    }
    Text {
        x: 16
        y: 8
        height: 56
        verticalAlignment: Text.AlignVCenter
        text: root.title
        color: palette.inkSurface
        font.family: M3Font.family
        font.pixelSize: M3Font.px(16)
        font.weight: 500
    }
    Rectangle {
        objectName: root.key + "Swatch"
        anchors.right: field.left
        anchors.rightMargin: 12
        y: 8 + 8 + 4
        width: 40
        height: 40
        radius: 20
        color: root.value !== "" ? root.value : root.fallback
        border.width: 1
        border.color: palette.outline
    }
    OutlinedField {
        id: field
        objectName: root.key
        anchors.right: parent.right
        anchors.rightMargin: 16
        y: 8
        width: 132
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        label: "Hex"
        placeholder: "Auto"
        text: root.value
        accessName: root.title + " colour"
        onTextEdited: (value) => {
            if (value === "" || /^#[0-9a-fA-F]{6}$/.test(value))
                root.edited(value)
        }
    }
    onValueChanged: if (!field.activeFocus || field.text === "") field.text = value
    Text {
        objectName: root.key + "Hint"
        visible: root.bad
        anchors.right: parent.right
        anchors.rightMargin: 16
        y: 68
        text: "Use a colour like #1a1c20."
        color: palette.error
        font.family: M3Font.family
        font.pixelSize: M3Font.px(12)
    }
}
