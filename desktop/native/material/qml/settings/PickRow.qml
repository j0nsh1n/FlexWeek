import QtQuick
import components 1.0
import "../sheets"

// A title, a helper line and a drop-down list (for more choices than a segmented button holds). Under a
// narrow width the list drops below the text.
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
    // [{label, value}]
    property var choices: []
    property string current: ""
    signal chosen(string value)
    objectName: "row_" + key

    readonly property int padV: density === "compact" ? 10 : 16
    readonly property int textHeight: M3Font.px(24) + (subtitle === "" ? 0 : M3Font.px(20))
    readonly property bool stacked: Math.max(titleText.implicitWidth, Math.min(subtitleText.implicitWidth, 240)) + pick.implicitWidth + 64 > width
    implicitHeight: stacked ? padV * 2 + textHeight + 8 + pick.height : Math.max(56, padV * 2 + textHeight)
    height: implicitHeight

    M3Palette { id: palette; theme: root.theme }

    Rectangle {
        visible: root.showDivider
        width: parent.width
        height: root.highContrast ? 1.5 : 1
        color: root.highContrast ? palette.outline : palette.outlineVariant
    }
    Column {
        id: titleBlock
        x: 16
        y: root.padV
        width: root.stacked ? root.width - 32 : root.width - 32 - pick.width - 16
        Text {
            id: titleText
            width: parent.width
            height: M3Font.px(24)
            verticalAlignment: Text.AlignVCenter
            text: root.title
            color: palette.inkSurface
            font.family: M3Font.family
            font.pixelSize: M3Font.px(16)
            font.weight: 500
            elide: Text.ElideRight
        }
        Text {
            id: subtitleText
            width: parent.width
            height: M3Font.px(20)
            visible: root.subtitle !== ""
            verticalAlignment: Text.AlignVCenter
            text: root.subtitle
            color: palette.inkMuted
            font.family: M3Font.family
            font.pixelSize: M3Font.px(14)
            elide: Text.ElideRight
        }
    }
    PickerField {
        id: pick
        objectName: root.key
        x: root.stacked ? 16 : root.width - width - 16
        y: root.stacked ? root.padV + root.textHeight + 8 : (root.height - height) / 2
        width: root.stacked ? Math.min(200, Math.max(0, root.width - 32)) : 200
        implicitWidth: 200
        theme: root.theme
        density: root.density
        reduceMotion: root.reduceMotion
        highContrast: root.highContrast
        options: root.choices
        value: root.current
        accessName: root.title
        onPicked: (value) => root.chosen(value)
    }
    // Picking sets the field's own value, which ends its binding: follow the saved one again.
    onCurrentChanged: pick.value = current
    Connections {
        target: Ui.settings
        function onChanged() { pick.value = root.current }
    }
}
